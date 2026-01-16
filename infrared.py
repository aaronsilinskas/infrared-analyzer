"""
Core infrared communication library for pulse-based protocols.

This module provides abstract interfaces and concrete implementations for
infrared transmission and reception. It decouples protocol logic from hardware
by using abstract PulseReader and PulseWriter interfaces, allowing different
hardware implementations (e.g., CircuitPython's pulseio) to be plugged in.

Key Components:
    - PulseReader/PulseWriter: Hardware abstraction interfaces
    - InfraredTransmitter: Sends encoded data via infrared
    - InfraredSingleReceiver: Receives from a single IR sensor
    - InfraredMultiReceiver: Receives from multiple sensors with signal selection
"""

try:
    from typing import Callable
except ImportError:
    pass

from protocol import InfraredEncoder, InfraredDecoder


class PulseReader(object):
    """
    Abstract interface for reading infrared pulse durations.

    Implementations wrap hardware-specific pulse input mechanisms and provide
    a uniform interface for accessing received pulse data.
    """

    def read_pulse(self) -> int | None:
        """
        Read the next pulse duration from the input buffer.

        Returns:
            int | None: Pulse duration in microseconds, or None if no pulse
                       is available in the buffer
        """
        raise NotImplementedError("Subclasses must implement read_pulse method")


class PulseWriter(object):
    """
    Abstract interface for writing infrared pulse sequences.

    Implementations wrap hardware-specific pulse output mechanisms and provide
    a uniform interface for transmitting infrared signals.
    """

    def write_pulses(self, durations: list[int]) -> None:
        """
        Transmit a sequence of pulse durations via infrared.

        Args:
            durations: List of pulse durations in microseconds, alternating
                      between mark (ON) and space (OFF) states
        """
        raise NotImplementedError("Subclasses must implement write_pulses method")


class InfraredTransmitter(object):
    """
    Transmits encoded data via infrared using a protocol encoder.

    Converts byte data into protocol-specific pulse sequences and sends them
    through a PulseWriter. Supports optional writer override for multi-output
    scenarios (e.g., multiple IR LEDs).
    """

    def __init__(self, pulse_writer: PulseWriter, encoder: InfraredEncoder) -> None:
        """
        Initialize the infrared transmitter.

        Args:
            pulse_writer: Default PulseWriter instance for sending IR signals
            encoder: Protocol encoder for data-to-pulse conversion
        """
        self._pulse_writer = pulse_writer
        self._encoder = encoder

    def send(
        self,
        data: bytes | bytearray,
        pulse_writer_override: PulseWriter | None = None,
    ) -> None:
        """
        Encode and transmit data via infrared.

        Converts the data to pulse durations using the configured encoder,
        then transmits using either the default writer or an override.

        Args:
            data: Bytes to encode and transmit
            pulse_writer_override: Optional alternative writer for this transmission.
                                  Useful for directing output to specific IR LEDs.
        """
        durations = self._encoder.encode(data)

        if pulse_writer_override:
            pulse_writer_override.write_pulses(durations)
        else:
            self._pulse_writer.write_pulses(durations)


class InfraredReceiver(object):
    """
    Abstract base class for infrared receivers.

    Defines the interface for receiving and decoding infrared transmissions,
    along with quality metrics for the received signals.
    """

    def receive(self) -> bytearray | None:
        """
        Attempt to receive and decode infrared data.

        Returns:
            bytearray | None: Decoded data if a complete packet was received,
                            None if no complete packet is available
        """
        raise NotImplementedError("Subclasses must implement decode method")

    @property
    def last_error_margin(self) -> int | None:
        """
        Get the timing error margin from the last received packet.

        Returns:
            int | None: Maximum timing deviation in microseconds, or None if
                       no packet has been received
        """
        raise NotImplementedError("Subclasses must implement last_error_margin method")

    @property
    def last_signal_strength(self) -> float | None:
        """
        Get the signal quality metric from the last received packet.

        Returns:
            float | None: Signal strength from 0.0 (poor) to 1.0 (excellent),
                         or None if no packet has been received
        """
        raise NotImplementedError(
            "Subclasses must implement last_signal_strength method"
        )


class InfraredSingleReceiver(InfraredReceiver):
    """
    Receives infrared data from a single sensor.

    Processes pulses from one PulseReader through a protocol decoder,
    returning decoded data when a complete packet is received.
    """

    def __init__(
        self,
        pulse_reader: PulseReader,
        decoder: InfraredDecoder,
    ) -> None:
        """
        Initialize the single-sensor infrared receiver.

        Args:
            pulse_reader: PulseReader instance providing pulse durations
            decoder: Protocol decoder for interpreting pulses
        """
        self._pulse_reader = pulse_reader
        self._decoder = decoder

    def receive(self) -> bytearray | None:
        """
        Process available pulses and return decoded data if a packet is complete.

        Reads all available pulses from the reader, feeding them to the decoder
        until either a complete packet is decoded or no more pulses are available.

        Returns:
            bytearray | None: Decoded packet data, or None if no complete packet
        """
        next_pulse = self._pulse_reader.read_pulse()

        while next_pulse is not None:
            data = self._decoder.decode(next_pulse)
            if data is not None:
                return data

            next_pulse = self._pulse_reader.read_pulse()

        return None

    @property
    def last_error_margin(self) -> int | None:
        """
        Get timing error margin from the last decoded packet.

        Returns:
            int | None: Maximum timing deviation in microseconds
        """
        return self._decoder.last_error_margin

    @property
    def last_signal_strength(self) -> float | None:
        """
        Get signal quality from the last decoded packet.

        Returns:
            float | None: Signal strength from 0.0 to 1.0
        """
        return self._decoder.last_signal_strength


class InfraredMultiReceiver(InfraredReceiver):
    """
    Receives infrared data from multiple sensors with automatic signal selection.

    Processes pulses from multiple sensors simultaneously, each with its own
    decoder instance. When multiple sensors receive the same packet, selects
    the one with the best signal quality (lowest error margin).

    This is useful for applications requiring 360-degree coverage using multiple
    IR receivers, where the strongest signal should be chosen. This fixes the
    issue of signal blending and increased noise when multiple receivers share
    a single data line.
    """

    def __init__(
        self,
        pulse_readers: dict[str, PulseReader],
        decoder_factory: Callable[[], InfraredDecoder],
    ) -> None:
        """
        Initialize the multi-sensor infrared receiver.

        Args:
            pulse_readers: Dictionary mapping sensor names (e.g., "North", "East")
                          to PulseReader instances
            decoder_factory: Callable that creates a new decoder instance for
                           each sensor (ensures independent decoding state)
        """
        self._pulse_readers = pulse_readers
        # Dictionary mapping sensor names to decoder instances
        self._decoders = {name: decoder_factory() for name in pulse_readers.keys()}
        # Timing errors from last reception per sensor
        self._last_error_margins: dict[str, int] = {}
        # Signal quality from last reception per sensor
        self._last_signal_strengths: dict[str, float] = {}

    def receive(self) -> bytearray | None:
        """
        Process pulses from all sensors and return the best decoded packet.

        Reads one pulse from each sensor, decodes them independently, and when
        a complete packet is received from any sensor(s), returns the data from
        the sensor with the lowest error margin (best timing accuracy).

        Returns:
            bytearray | None: Decoded packet from the best sensor, or None if
                            no complete packet is available from any sensor
        """
        data_available = True

        while data_available:

            # Read one pulse from each sensor
            pulses = {}
            for name, pulse_reader in self._pulse_readers.items():
                next_pulse = pulse_reader.read_pulse()
                if next_pulse is not None:
                    pulses[name] = next_pulse

            if len(pulses) == 0:
                # No pulses from any sensor, exit loop
                data_available = False
                break

            # Decode each pulse
            datas = {}
            for name, pulse in pulses.items():
                data = self._decoders[name].decode(pulse)
                if data is not None:
                    datas[name] = data

            if len(datas) > 0:
                # A complete packet was received by one or more sensors
                # Record receiver stats
                self._last_error_margins = {}
                self._last_signal_strengths = {}
                for name, decoder in self._decoders.items():
                    if datas.get(name) is not None:
                        self._last_error_margins[name] = decoder.last_error_margin
                        self._last_signal_strengths[name] = decoder.last_signal_strength

                # Determine the best signal by minimum error margin
                min_error_margin: int = float("inf")
                best_receiver_name: str = None
                for name, error_margin in self._last_error_margins.items():
                    if error_margin < min_error_margin:
                        min_error_margin = error_margin
                        best_receiver_name = name

                # Reset all decoders for next packet
                for decoder in self._decoders.values():
                    decoder.reset(decoder.last_error_margin)

                # Return the data from the strongest signal
                return datas[best_receiver_name]

        return None

    @property
    def last_best_receiver(self) -> str | None:
        """
        Get the name of the sensor that received the best signal.

        Returns:
            str | None: Name of the sensor with lowest error margin, or None
                       if no packet has been received
        """
        min_error_margin: int = float("inf")
        best_receiver_name: str = None
        for name, error_margin in self._last_error_margins.items():
            if error_margin < min_error_margin:
                min_error_margin = error_margin
                best_receiver_name = name

        return best_receiver_name

    @property
    def last_receivers(self) -> list[str]:
        """
        Get list of sensors that received the last packet, ordered by quality.

        Returns:
            list[str]: Sensor names sorted by error margin (best first)
        """
        return sorted(
            self._last_error_margins.keys(),
            key=lambda name: self._last_error_margins[name],
        )

    @property
    def last_error_margin(self) -> int | None:
        """
        Get timing error margin from the best sensor's last reception.

        Returns:
            int | None: Error margin in microseconds from the best sensor
        """
        best_receiver_name = self.last_best_receiver
        if best_receiver_name is not None:
            return self._last_error_margins[best_receiver_name]

        return None

    @property
    def last_error_margins(self) -> dict[str, int]:
        """
        Get error margins from all sensors that received the last packet.

        Returns:
            dict[str, int]: Dictionary mapping sensor names to error margins,
                          sorted by error margin (best first)
        """
        return dict(sorted(self._last_error_margins.items(), key=lambda item: item[1]))

    @property
    def last_signal_strength(self) -> float | None:
        """
        Get signal strength from the best sensor's last reception.

        Returns:
            float | None: Signal strength (0.0-1.0) from the best sensor
        """
        best_receiver_name = self.last_best_receiver
        if best_receiver_name is not None:
            return self._last_signal_strengths[best_receiver_name]

        return None

    @property
    def last_signal_strengths(self) -> dict[str, float]:
        """
        Get signal strengths from all sensors that received the last packet.

        Returns:
            dict[str, float]: Dictionary mapping sensor names to signal strengths,
                            sorted by strength (strongest first)
        """
        return dict(
            sorted(
                self._last_signal_strengths.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        )
