from typing import Dict, Sequence, Type

from pydatalab.apps.chat.blocks import ChatBlock
from pydatalab.apps.echem import CycleBlock
from pydatalab.apps.eis import EISBlock
from pydatalab.apps.raman import RamanBlock
from pydatalab.apps.tga import MassSpecBlock
from pydatalab.apps.xrd import XRDBlock
from pydatalab.blocks.blocks import (
    CommentBlock,
    DataBlock,
    MediaBlock,
    NMRBlock,
    NotSupportedBlock,
)

BLOCKS: Sequence[Type[DataBlock]] = (
    DataBlock,
    CommentBlock,
    MediaBlock,
    XRDBlock,
    CycleBlock,
    RamanBlock,
    NMRBlock,
    MassSpecBlock,
    NotSupportedBlock,
    ChatBlock,
    EISBlock,
)

BLOCK_TYPES: Dict[str, Type[DataBlock]] = {block.blocktype: block for block in BLOCKS}
BLOCK_TYPES["test"] = DataBlock

__all__ = (
    "DataBlock",
    "CommentBlock",
    "MediaBlock",
    "XRDBlock",
    "ChatBlock",
    "EISBlock",
    "CycleBlock",
    "NMRBlock",
    "RamanBlock",
    "MassSpecBlock",
    "BLOCK_TYPES",
    "BLOCKS",
)
