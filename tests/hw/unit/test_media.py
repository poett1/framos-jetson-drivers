import pytest

from lib.media import parse_topology, topology_ok

pytestmark = pytest.mark.unit

MEDIA_CTL_P = """Media controller API version 6.8.12

Media device information
------------------------
driver          tegra-camrtc-ca
model           NVIDIA Tegra Video Input Device

Device topology
- entity 1: nvcsi--1 (2 pads, 2 links, 0 routes)
            type V4L2 subdev subtype Unknown flags 0
            device node name /dev/v4l-subdev0
\tpad0: Sink
\t\t<- "imx900 9-001a":0 [ENABLED]
\tpad1: Source
\t\t-> "vi-output, imx900 9-001a":0 [ENABLED]

- entity 4: imx900 9-001a (1 pad, 1 link, 0 routes)
            type V4L2 subdev subtype Sensor flags 0
            device node name /dev/v4l-subdev1
\tpad0: Source
\t\t[stream:0 fmt:SRGGB12_1X12/2064x1552 field:none colorspace:srgb]
\t\t-> "nvcsi--1":0 [ENABLED]

- entity 6: vi-output, imx900 9-001a (1 pad, 1 link, 0 routes)
            type Node subtype V4L flags 0
            device node name /dev/video0
\tpad0: Sink
\t\t<- "nvcsi--1":1 [ENABLED]
"""


def test_parse_topology():
    ents = parse_topology(MEDIA_CTL_P)
    assert ents["imx900 9-001a"].devnode == "/dev/v4l-subdev1"
    assert ents["vi-output, imx900 9-001a"].devnode == "/dev/video0"
    assert ents["vi-output, imx900 9-001a"].upstream == ["nvcsi--1"]
    assert ents["nvcsi--1"].upstream == ["imx900 9-001a"]


def test_topology_ok():
    ents = parse_topology(MEDIA_CTL_P)
    assert topology_ok(ents, "imx900 9-001a")
    assert not topology_ok(ents, "imx900 10-001a")


def test_topology_disabled_link_is_not_ok():
    ents = parse_topology(MEDIA_CTL_P.replace('<- "imx900 9-001a":0 [ENABLED]', '<- "imx900 9-001a":0 []'))
    assert not topology_ok(ents, "imx900 9-001a")
