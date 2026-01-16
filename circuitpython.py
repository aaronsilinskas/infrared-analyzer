"""
CircuitPython-specific implementations of infrared pulse readers and writers.

This module provides concrete implementations of the PulseReader and PulseWriter
abstract classes that wrap CircuitPython's pulseio module, allowing infrared
communication without direct dependencies on pulseio in the core infrared module.
"""

import pulseio
from infrared import PulseReader, PulseWriter


class PulseInReader(PulseReader):
    """
    A PulseReader implementation that reads from a CircuitPython PulseIn object.

    This class wraps a pulseio.PulseIn instance and provides pulse durations
    via the read_pulse() method.
    """

    def __init__(self, pulsein: pulseio.PulseIn):
        """
        Initialize the PulseInReader with a PulseIn object.

        Args:
            pulsein: A pulseio.PulseIn instance configured for infrared reception
        """
        self._pulsein = pulsein

    def read_pulse(self) -> int | None:
        """
        Read the next pulse duration from the buffer.

        Returns the oldest pulse duration and removes it from the buffer.
        If no pulses are available, returns None.

        Returns:
            int | None: Pulse duration in microseconds, or None if buffer is empty
        """
        if len(self._pulsein) > 0:
            return self._pulsein.popleft()

        return None


class PulseOutWriter(PulseWriter):
    """
    A PulseWriter implementation that writes to a CircuitPython PulseOut object.

    This class wraps a pulseio.PulseOut instance and transmits infrared signals
    by sending pulse duration arrays via the write_pulses() method.
    """

    def __init__(self, pulseout: pulseio.PulseOut):
        """
        Initialize the PulseOutWriter with a PulseOut object.

        Args:
            pulseout: A pulseio.PulseOut instance configured with the appropriate
                     carrier frequency (typically 38kHz for infrared)
        """
        self._pulseout = pulseout

    def write_pulses(self, pulses: list[int]) -> None:
        """
        Transmit a sequence of pulse durations.

        Sends the pulse sequence to the infrared LED via the underlying
        PulseOut object. The pulses alternate between ON and OFF states,
        with the carrier frequency modulating the ON pulses.

        Args:
            pulses: List of pulse durations in microseconds. The first pulse
                   is typically ON (mark), followed by OFF (space), alternating.
        """
        self._pulseout.send(pulses)
