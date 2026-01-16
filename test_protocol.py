from protocol import InfraredEncoder, InfraredDecoder
import array

IR_UNIT = 500
IR_ERROR_MARGIN = IR_UNIT / 2

IR_HEADER_MARK = IR_UNIT * 8
IR_HEADER_SPACE = IR_UNIT * 6

IR_ZERO = IR_UNIT
IR_ONE = IR_UNIT * 3
IR_LEAD_OUT = IR_UNIT * 10

IR_CRC_GENERATOR = 0x1D


def _calculate_crc(data: bytes | bytearray) -> int:
    crc = 0
    for data_byte in data:
        crc ^= data_byte
        for j in range(8):
            if crc & 0x80 != 0:
                crc = ((crc << 1) & 0xFF) ^ IR_CRC_GENERATOR
            else:
                crc = (crc << 1) & 0xFF
    return crc


class TestEncoder(InfraredEncoder):
    def __init__(self) -> None:
        pass

    def encode(self, data: bytes | bytearray) -> array.array:
        # length = header + (data * 8 bits per byte) + crc bits + lead out
        durations = array.array("H", [0] * (2 + len(data) * 8 + 8 + 1))
        durations[0] = IR_HEADER_MARK
        durations[1] = IR_HEADER_SPACE
        durations[-1] = IR_LEAD_OUT

        duration_index = 2
        for data_byte in data:
            self._encode_byte(durations, duration_index, data_byte)
            duration_index += 8

        crc = _calculate_crc(data)
        # print("CRC: ", bin(crc))
        self._encode_byte(durations, duration_index, crc)

        return durations

    def _encode_byte(
        self, durations: array.array, duration_index: int, value: int
    ) -> None:
        for i in range(8):
            if (value & 0x80) > 0:
                durations[duration_index] = IR_ONE
            else:
                durations[duration_index] = IR_ZERO
            value <<= 1
            duration_index += 1


class MWDecoder(InfraredDecoder):

    def __init__(self):
        super().__init__(IR_ERROR_MARGIN)

    def decode(self, pulse: int) -> bytearray | None:
        # print("Pulse: ", pulse)

        # discard pulses until we get the first header pulse
        if self.decoder_state == 0:
            if self.check_pulse(pulse, IR_HEADER_MARK):
                self.decoder_state = 1
        elif self.decoder_state == 1:
            if self.check_pulse(pulse, IR_HEADER_SPACE):
                self.decoder_state = 2
            else:
                self.reset(IR_ERROR_MARGIN)
        elif self.decoder_state == 2:
            if self.check_pulse(pulse, IR_ONE):
                self.write_bit(1)
            elif self.check_pulse(pulse, IR_ZERO):
                self.write_bit(0)
            elif self.check_pulse(pulse, IR_LEAD_OUT):
                data = self.received_data

                if len(data) < 2:
                    # no CRC or data, packet is corrupt so reset
                    self.reset(IR_ERROR_MARGIN)
                    return None

                received_crc = data[-1]
                data_without_crc = data[: len(data) - 1]
                calculated_crc = _calculate_crc(data_without_crc)

                self.reset(self._max_error_margin)

                if received_crc == calculated_crc:
                    return data_without_crc
                else:
                    print("CRC mismatch: ", bin(received_crc), bin(calculated_crc))
            else:
                # unknown pulse while receiving data, packet is corrupt so reset
                self.reset(IR_ERROR_MARGIN)
