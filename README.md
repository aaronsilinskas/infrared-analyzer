# infrared-analyzer

A test tool for infrared receivers, written in CircuitPython.

It listens on up to four infrared receivers at once, decodes each one separately, and for every packet prints which receiver heard it best and how clean the signal was. It can also send packets from an infrared LED.

It was built for [Aura](https://mindwidgets.com), a real-world adventure game platform, to find out how to place receivers on a device so that it reliably notices an infrared tag hit from any side.

## What you need

- A CircuitPython board with `pulseio`. The pins in `code.py` are for an RP2040 Feather.
- One to four 38 kHz infrared receiver modules. We used the Vishay TSOP33338 and TSOP38238.
- To send: an infrared LED with a transistor to drive it, on a 38 kHz carrier. We used the Vishay TSAL6400.
- Something that sends packets to listen to: a second board running this code, or infrared tag gear that uses the same protocol.

No extra libraries are needed.

## Wiring

Each receiver gets its own data pin. `code.py` uses these:

| Name in the output | Pin |
| ------------------ | --- |
| `Left` | `D12` |
| `Right` | `D6` |
| `Front` | `D10` |
| `NA` | `SCK` |

The LED driver is on `MISO`.

On an RP2040, each of these pins is on a separate PWM channel. Change the pins and names at the top of `code.py` to suit your board, and remove any receivers you don't have.

## Run a test

1. Copy the `.py` files to the board's `CIRCUITPY` drive.
2. Open a serial console.
3. Send infrared packets at the receivers from different distances and angles.

For every packet received, the tool prints:

- **IR Data Received**: the decoded bytes.
- **MARGIN**: the largest timing error in the packet, in microseconds, on the receiver that heard it best. Lower is better.
- **STRENGTH**: the same thing as a score from 0 to 1, where 1 is a clean signal.
- **BEST**: the name of the receiver that heard it best.
- **MARGINS**: the timing error on every receiver that decoded the packet, best first.
- **Tag Data**: the team, player, and damage carried by the packet.

A divider line is printed every three seconds so that separate attempts are easy to tell apart in the log.

To make the board send as well, uncomment the transmit block in `code.py`. It sends one packet every three seconds.

### Protocols

The tool decodes with `TagInfraredDecoder` (`tag_protocol.py`), a 7-bit infrared tag packet: team, player, and damage.

- `test_protocol.py` has a second protocol with a CRC check, for sending any bytes.
- `LoggingInfraredDecoder` (`protocol.py`) prints the raw pulse lengths, which is useful when working out an unknown signal.

To add your own, subclass `InfraredEncoder` and `InfraredDecoder` in `protocol.py`.

## What we learned

These are observations from bench tests indoors in January 2026. They are not specifications.

- **Give each receiver its own data pin.** In an earlier test, four receivers wired to one pin gave a signal only as good as the worst of them, because a reflected copy of the signal blends with the direct one. With one pin and one decoder per receiver, the tool simply uses the cleanest copy.
- **An RP2040 can handle it.** Four receiver inputs and one LED output worked together.
- **Hits are easy to detect.** If anything the receivers were too sensitive, and will need a cover to cut them down.
- **Hit direction is hard.** With TSOP33338 receivers we found no reliable link between where a signal came from and what the receivers reported. Indoors, reflections off the walls reach every receiver.
- **Hoods help, a little.** Small hoods of black card around each receiver gave a correct direction up close. In a box with one receiver on the front and one on each side, the side receivers worked fairly well once they were hooded against signals from the front.
- **A wide LED suits wide spells.** The TSAL6400, with a 25° half-angle, gave a good cone.

This tool measures signal quality, not distance. No range figures are given here.

## License

MIT. See [LICENSE](LICENSE).
