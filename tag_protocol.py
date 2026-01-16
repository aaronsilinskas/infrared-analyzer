"""
Infrared protocol implementation for laser tag communication.

This module implements a custom infrared protocol for transmitting laser tag
game data including team, player, and damage information. The protocol uses
pulse-width modulation to encode 7 bits of data with a distinctive preamble.

Protocol Specification:
    - Preamble: 3000μs mark, 6000μs space, 3000μs mark
    - Data encoding: Manchester-like with 2000μs marks
    - Bit 0: 2000μs mark + 1000μs space
    - Bit 1: 2000μs mark + 2000μs space
    - Data format: 2-bit team, 3-bit player, 2-bit damage
    - Error tolerance: ±500μs

For unmanaged games:
Player 1 represents SOLO mode
Player 2 represents TEAM 1
Player 3 represents TEAM 2
"""

import array
from protocol import InfraredDecoder, InfraredEncoder

# Timing constants in microseconds
TAG_ERROR_MARGIN = 500  # Maximum allowed timing deviation
TAG_PREAMBLE = [3000, 6000, 3000]  # Laser tag start sequence

TAG_MARK = 2000  # Duration of mark (ON) pulse for data bits
TAG_SPACE_ZERO = 1000  # Duration of space (OFF) pulse for bit 0
TAG_SPACE_ONE = 2000  # Duration of space (OFF) pulse for bit 1

# Data field bit lengths
TAG_TEAM_BITS = 2  # 2 bits = 4 teams (0-3)
TAG_PLAYER_BITS = 3  # 3 bits = 8 players (1-8)
TAG_DAMAGE_BITS = 2  # 2 bits = 4 damage levels (1-4)
TAG_DATA_BITS = TAG_TEAM_BITS + TAG_PLAYER_BITS + TAG_DAMAGE_BITS
TAG_TOTAL_PULSES = len(TAG_PREAMBLE) + TAG_DATA_BITS * 2


class TagData:
    """
    Container for laser tag shot data.

    Attributes:
        team: Team number (0-3)
        player: Player number (1-8)
        damage: Damage amount (1-4)
    """

    def __init__(self, team: int, player: int, damage: int) -> None:
        """
        Initialize tag data.

        Args:
            team: Team identifier (0-3)
            player: Player identifier (1-8)
            damage: Damage value (1-4)
        """
        self.team = team
        self.player = player
        self.damage = damage


def decode_tag_data(data: bytes | bytearray) -> TagData:
    """
    Decode a byte into TagData fields.

    Extracts team, player, and damage information from the encoded byte.
    The byte format is: [padding(1)] [team(2)] [player(3)] [damage(2)]

    Args:
        data: Single byte containing encoded tag information

    Returns:
        TagData: Decoded tag shot information

    Raises:
        ValueError: If data is empty
    """
    if len(data) < 1:
        raise ValueError("Expecting 1 byte of tag data.")

    byte = data[0]
    team = (byte >> 5) & 0b11  # Extract bits 6-5
    player = 1 + ((byte >> 2) & 0b111)  # Extract bits 4-2, add 1 for range 1-8
    damage = 1 + (byte & 0b11)  # Extract bits 1-0, add 1 for range 1-4

    return TagData(team, player, damage)


def encode_tag_data(tag_data: TagData) -> bytearray:
    """
    Encode TagData fields into a byte.

    Packs team, player, and damage information into a single byte.
    The byte format is: [padding(1)] [team(2)] [player(3)] [damage(2)]

    Args:
        tag_data: Tag information to encode

    Returns:
        bytearray: Single byte containing encoded tag information

    Raises:
        ValueError: If any field is out of valid range
    """
    if tag_data.team < 0 or tag_data.team > 3:
        raise ValueError("Team must be between 0 and 3.")
    if tag_data.player < 1 or tag_data.player > 8:
        raise ValueError("Player must be between 1 and 8.")
    if tag_data.damage < 1 or tag_data.damage > 4:
        raise ValueError("Damage must be between 1 and 4.")

    # Pack fields into byte: [padding(1)][team(2)][player-1(3)][damage-1(2)]
    byte = (tag_data.team & 0b11) << 5
    byte |= ((tag_data.player - 1) & 0b111) << 2
    byte |= (tag_data.damage - 1) & 0b11

    return bytearray([byte])


class TagInfraredDecoder(InfraredDecoder):
    """
    Decoder for the laser tag infrared protocol.

    Decodes incoming infrared pulses into tag data bytes. Uses a state machine
    to validate the preamble, then decode data bits based on pulse widths.
    """

    def __init__(self) -> None:
        """Initialize the tag decoder with protocol-specific error margin."""
        super().__init__(TAG_ERROR_MARGIN)

    def decode(self, pulse: int) -> bytearray | None:
        """
        Process a single pulse and return decoded tag data if complete.

        State machine progression:
        - States 0-2: Validate preamble pulses
        - States 3+: Decode data bits (mark then space for each bit)

        Args:
            pulse: Pulse duration in microseconds

        Returns:
            bytearray | None: Single byte of decoded tag data if packet is
                            complete, None if more pulses needed or error occurred
        """
        if self.decoder_state < len(TAG_PREAMBLE):
            # Validate preamble sequence
            expected_pulse = TAG_PREAMBLE[self.decoder_state]
            if self.check_pulse(pulse, expected_pulse):
                self.decoder_state += 1
            else:
                self.reset(TAG_ERROR_MARGIN)
        elif self.decoder_state < TAG_TOTAL_PULSES:            
            # Decode data bits
            bit_index = self.decoder_state - len(TAG_PREAMBLE)
            if bit_index % 2 == 0:
                # Even index: expecting mark pulse
                if not self.check_pulse(pulse, TAG_MARK):
                    # Unexpected pulse duration, reset decoder
                    self.reset(TAG_ERROR_MARGIN)
                    
                    return None
            else:
                # Odd index: expecting space pulse (determines bit value)
                if self.check_pulse(pulse, TAG_SPACE_ONE):
                    self.write_bit(1)
                elif self.check_pulse(pulse, TAG_SPACE_ZERO):
                    self.write_bit(0)
                else:
                    # Unexpected pulse duration, reset decoder                    
                    self.reset(TAG_ERROR_MARGIN)
                    
                    return None
            self.decoder_state += 1
        elif self.decoder_state == TAG_TOTAL_PULSES:
            # Packet complete: add padding bit to push bits into received_data
            self.write_bit(0)
            # Extract tag data byte and remove padding bit
            tag_data = self.received_data[0] >> 1
            self.reset(self._max_error_margin)

            return bytearray([tag_data])
        else:
            # Unknown state: reset decoder
            self.reset(TAG_ERROR_MARGIN)


class TagInfraredEncoder(InfraredEncoder):
    """
    Encoder for the laser tag infrared protocol.

    Converts tag data bytes into pulse sequences for infrared transmission.
    Adds the protocol preamble and encodes each bit using pulse-width modulation.
    """

    def encode(self, data: bytes | bytearray) -> array.array:
        """
        Encode tag data byte into infrared pulse sequence.

        Generates a pulse array containing:
        1. Preamble (3000, 6000, 3000 μs)
        2. Data bits encoded as mark+space pairs

        Args:
            data: Single byte containing encoded tag information

        Returns:
            array.array: Sequence of pulse durations in microseconds,
                        alternating between mark (ON) and space (OFF)
        """
        # Allocate array for preamble + data bits
        durations = array.array("H", [0] * (len(TAG_PREAMBLE) + TAG_DATA_BITS * 2))
        duration_index = 0

        # Add preamble
        for pulse in TAG_PREAMBLE:
            durations[duration_index] = pulse
            duration_index += 1

        # Prepare data: shift left by 1 to use only upper 7 bits
        tag_data = data[0]
        tag_data <<= 1  # Ignore most significant padding bit

        # Encode each data bit as mark + space
        for i in range(TAG_DATA_BITS):
            durations[duration_index] = TAG_MARK
            duration_index += 1

            # Space duration determines bit value
            if (tag_data & 0x80) > 0:
                durations[duration_index] = TAG_SPACE_ONE  # Bit 1
            else:
                durations[duration_index] = TAG_SPACE_ZERO  # Bit 0

            # Move next bit to most significant position
            tag_data <<= 1
            duration_index += 1

        return durations
