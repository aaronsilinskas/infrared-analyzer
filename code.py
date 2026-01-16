import time
import board
from protocol import LoggingInfraredDecoder
import pulseio
from infrared import InfraredSingleReceiver, InfraredMultiReceiver, InfraredTransmitter
from tag_protocol import (
    TagInfraredDecoder,
    TagInfraredEncoder,
    decode_tag_data,
    encode_tag_data,
    TagData,
)
from circuitpython import PulseInReader, PulseOutWriter

# Infrared Setup
# NOTE: Pins chosen to give each pin a separate PWM channel on RP2040
ir_pulse_readers = {
    "Left": PulseInReader(pulseio.PulseIn(board.D12, maxlen=256, idle_state=True)),
    "NA": PulseInReader(pulseio.PulseIn(board.SCK, maxlen=256, idle_state=True)),
    "Right": PulseInReader(pulseio.PulseIn(board.D6, maxlen=256, idle_state=True)),
    "Front": PulseInReader(pulseio.PulseIn(board.D10, maxlen=256, idle_state=True)),
}

ir_pulseout = pulseio.PulseOut(board.MISO, frequency=38000, duty_cycle=2**15)
# aoe_ir_pulseout = pulseio.PulseOut(board.D11, frequency=38000, duty_cycle=2**15)

# infrared_receiver = InfraredSingleReceiver(
#     ir_pulse_readers["West"], decoder=TagInfraredDecoder()
# )

infrared_receiver = InfraredMultiReceiver(
    ir_pulse_readers, decoder_factory=lambda: TagInfraredDecoder()
)

infrared_transmitter = InfraredTransmitter(
    PulseOutWriter(ir_pulseout), encoder=TagInfraredEncoder()
)

last_tick = time.monotonic()

next_transmit = time.monotonic()

next_marker = time.monotonic()

while True:
    elapsed_time = time.monotonic() - last_tick
    last_tick = time.monotonic()

    data = infrared_receiver.receive()
    if data is not None:
        print(
            "IR Data Received: ",
            [hex(b) for b in data],
            " MARGIN:  ",
            infrared_receiver.last_error_margin,
            " STRENGTH: ",
            infrared_receiver.last_signal_strength,
            " BEST: ",
            getattr(infrared_receiver, "last_best_receiver", None),
            " MARGINS: ",
            getattr(infrared_receiver, "last_error_margins", None),
        )

        tag_data = decode_tag_data(data)
        print(
            f" Tag Data - Team: {tag_data.team}, Player: {tag_data.player}, Damage: {tag_data.damage}"
        )

    # if next_transmit < time.monotonic():
    #     next_transmit = time.monotonic() + 3.0
    #     print("Transmitting IR Tag Signal")

    #     data = encode_tag_data(TagData(team=0, player=1, damage=1))
    #     print("Encoded Tag Data: ", [bin(b) for b in data])

    #     infrared_transmitter.send(data)

    if next_marker < time.monotonic():
        next_marker = time.monotonic() + 3.0
        print(f"_-^^-_-^^-_-^^-_-^^-_-^^-_-^^-_-^^-_-^^-_")
