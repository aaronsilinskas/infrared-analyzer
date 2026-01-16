"""
Abstract base classes for infrared protocol encoding and decoding.

This module defines the core interfaces for implementing infrared communication
protocols. Encoders convert data to pulse sequences, while decoders convert
incoming pulses back to data, handling timing variations and error detection.
"""

from array import array


class InfraredEncoder(object):
    """
    Abstract base class for encoding data into infrared pulse sequences.

    Subclasses must implement the encode method to convert byte data into
    an array of pulse durations that can be transmitted via infrared.
    """

    def encode(self, data: bytes | bytearray) -> array:
        """
        Encode byte data into a sequence of pulse durations.

        Args:
            data: The bytes to encode into an infrared signal

        Returns:
            array: Array of pulse durations in microseconds, alternating
                  between mark (ON) and space (OFF) states
        """
        raise NotImplementedError("Subclasses must implement encode method")


class InfraredDecoder(object):
    """
    Abstract base class for decoding infrared pulse sequences into data.

    This class provides a stateful decoder that processes incoming pulses
    one at a time, tracking error margins and maintaining decoder state.
    Subclasses implement protocol-specific pulse interpretation.
    """

    def __init__(self, error_threshold: int) -> None:
        """
        Initialize the decoder with an error threshold.

        Args:
            error_threshold: Maximum allowed timing deviation in microseconds.
                           Pulses with deviations larger than this are rejected.
        """
        # Maximum timing deviation allowed for pulse matching
        self._error_threshold = error_threshold

        # Current state in the decoding state machine
        self._decoder_state: int = 0
        # Buffer for accumulating decoded bytes
        self._received_data: bytearray = bytearray()
        # Current bit position being written (7 to 0)
        self._received_bit_index: int = 0
        # Current byte being assembled from bits
        self._received_byte: int = 0

        # Largest timing error seen in current packet
        self._max_error_margin: int = 0
        # Error margin from the most recent decoded packet
        self._last_error_margin: int = 0

    def decode(self, pulse: int) -> bytearray | None:
        """
        Process a single pulse and return decoded data if a packet is complete.

        Args:
            pulse: Pulse duration in microseconds

        Returns:
            bytearray | None: Decoded data if a complete packet was received,
                            otherwise None if no pulses were received, if more
                            pulses are needed, or an error occurred
        """
        raise NotImplementedError("Subclasses must implement decode method")

    def reset(self, error_margin: int) -> None:
        """
        Reset the decoder state for processing a new packet.

        Called after successfully decoding a packet or when an error occurs.
        Clears all buffers and resets state machine.

        Args:
            error_margin: The error margin to record for the current packet
        """
        self._decoder_state = 0
        self._received_data = bytearray()
        self._reset_bit_writer()

        self._max_error_margin = 0
        self._last_error_margin = error_margin

    def check_pulse(self, received: int, expected: int) -> bool:
        """
        Check if a received pulse matches the expected duration within tolerance.

        Compares the received pulse duration against the expected value,
        allowing for timing variations up to the error threshold. Tracks
        the maximum error margin seen during successful matches.

        Args:
            received: Actual pulse duration in microseconds
            expected: Expected pulse duration in microseconds

        Returns:
            bool: True if the pulse matches within the error threshold,
                 False otherwise
        """
        margin = abs(received - expected)
        match = margin < self._error_threshold
        if match:
            self._max_error_margin = max(self._max_error_margin, margin)
        return match

    def write_bit(self, bit: int) -> None:
        """
        Write a decoded bit to the current byte buffer.

        Bits are written from MSB (bit 7) to LSB (bit 0). When a complete
        byte is assembled, it's appended to the received_data buffer and
        the bit writer is reset for the next byte.

        Args:
            bit: The bit value to write (0 or 1)
        """
        if bit == 1:
            self._received_byte |= 1 << self._received_bit_index

        self._received_bit_index -= 1
        if self._received_bit_index < 0:
            # print("Received Byte: ", bin(self._received_byte))
            self._received_data.append(self._received_byte)
            self._reset_bit_writer()
        # print("Bit Update: ", bin(self._received_byte), self._received_bit_index)

    def _reset_bit_writer(self) -> None:
        """
        Reset the bit writer state for a new byte.

        Clears the current byte buffer and resets the bit index to 7 (MSB).
        """
        self._received_byte = 0
        self._received_bit_index = 7

    @property
    def decoder_state(self) -> int:
        """
        Get the current decoder state machine state.

        Returns:
            int: Current state value (protocol-specific meaning)
        """
        return self._decoder_state

    @decoder_state.setter
    def decoder_state(self, value: int) -> None:
        """
        Set the decoder state machine state.

        Args:
            value: New state value
        """
        self._decoder_state = value

    @property
    def received_data(self) -> bytearray:
        """
        Get the buffer of decoded bytes accumulated so far.

        Returns:
            bytearray: Bytes decoded in the current packet
        """
        return self._received_data

    @property
    def last_error_margin(self) -> int | None:
        """
        Get the maximum error margin from the last decoded packet.

        This represents the worst-case timing deviation that was still
        within the acceptable threshold for the most recent packet.

        Returns:
            int | None: Maximum error margin in microseconds, or None if
                       no packet has been decoded yet
        """
        return self._last_error_margin

    @property
    def last_signal_strength(self) -> float | None:
        """
        Calculate signal quality based on timing accuracy of last packet.

        Returns a value between 0 and 1, where 1.0 indicates perfect timing
        and lower values indicate increasing timing errors. An error ratio
        of 30% or less of the threshold is considered full strength.

        Returns:
            float | None: Signal strength from 0.0 to 1.0, or None if no
                         packet has been decoded yet
        """
        if self._last_error_margin == 0:
            return 1.0

        # Calculate the signal strength based on how close the last error margin was to the error threshold
        error_ratio = self._last_error_margin / self._error_threshold
        # Clamp signal strength between 0 and 1, where an error ratio of 30% or less is considered full strength
        signal_strength = min(1, 1.3 - error_ratio)

        return signal_strength


class LoggingInfraredDecoder(InfraredDecoder):
    """
    A debugging decoder that logs all incoming pulses without decoding.

    This decoder can be used for protocol analysis and debugging by
    observing raw pulse sequences without attempting to interpret them.
    """

    def __init__(self) -> None:
        """
        Initialize the logging decoder with no error threshold.

        Since this decoder doesn't perform actual decoding, no error
        threshold is needed.
        """
        super().__init__(0)  # No error threshold needed for logging

    def decode(self, pulse: int) -> bytearray | None:
        """
        Log the pulse without decoding it.

        Args:
            pulse: Pulse duration in microseconds

        Returns:
            None: This decoder never returns data
        """
        print("Pulse", pulse)

        return None
