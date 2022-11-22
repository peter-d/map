from typing import Callable, ClassVar, List, Optional, Union

class Transaction:
    ANNOTATION_TYPE_STR: ClassVar[str] = ...
    CONTINUE_FLAG: ClassVar[int] = ...
    FLAGS_MASK_TYPE: ClassVar[int] = ...
    INSTRUCTION_TYPE_STR: ClassVar[str] = ...
    MEMORY_OP_TYPE_STR: ClassVar[str] = ...
    PAIR_TYPE_STR: ClassVar[str] = ...
    def __init__(self, trans_ptr: int, is_proxy: bool) -> None: ...
    def contains(self, hc: int) -> bool: ...
    def containsInterval(self, l: int, r: int) -> bool: ...
    def getAnnotation(self) -> Optional[str]: ...
    def getAnnotationLength(self) -> Optional[int]: ...
    def getComponentID(self) -> Optional[int]: ...
    def getDisplayID(self) -> Optional[int]: ...
    def getFlags(self) -> Optional[int]: ...
    def getLeft(self) -> int: ...
    def getLocationID(self) -> Optional[int]: ...
    def getOpcode(self) -> Optional[int]: ...
    def getPairID(self) -> Optional[int]: ...
    def getParentTransactionID(self) -> Optional[int]: ...
    def getRealAddress(self) -> Optional[int]: ...
    def getRight(self) -> int: ...
    def getTransactionID(self) -> Optional[int]: ...
    def getType(self) -> int: ...
    def getTypeString(self) -> str: ...
    def getVirtualAddress(self) -> Optional[int]: ...
    def isContinued(self) -> bool: ...
    def isProxy(self) -> bool: ...
    def isValid(self) -> bool: ...
    def makeRealCopy(self) -> Transaction: ...

class TransactionDatabase:
    OBJECT_DESTROYED_ERROR: ClassVar[str] = ...
    def __init__(self, filename: str, num_locs: int, update_enabled: bool) -> None: ...
    def ackUpdate(self) -> None: ...
    def clearCurrentTickContent(self) -> None: ...
    def disableUpdate(self) -> None: ...
    def enableUpdate(self) -> None: ...
    def forceUpdate(self) -> None: ...
    def getChunkSize(self) -> int: ...
    def getDisplayID(self) -> Optional[int]: ...
    def getFileEnd(self) -> int: ...
    def getFileInclusiveEnd(self) -> int: ...
    def getFileStart(self) -> int: ...
    def getFileVersion(self) -> int: ...
    def getLocationMap(self) -> List[Union[int, str]]: ...
    def getNodeDump(self, node_idx: int, loc_start: int = 0, loc_end: int = 0, tick_entry_limit: int = 0) -> str: ...
    def getNodeLength(self) -> int: ...
    def getNodeStates(self) -> str: ...
    def getNumCachedAnnotations(self) -> int: ...
    def getPairID(self, loc: int) -> Optional[int]: ...
    def getSizeInBytes(self) -> int: ...
    def getTransactionAnnotation(self, loc: int) -> Optional[str]: ...
    def getTransactionID(self, loc: int) -> Optional[int]: ...
    def getTransactionProxy(self, loc: int) -> Transaction: ...
    def getVerbose(self) -> bool: ...
    def getWindowLeft(self) -> int: ...
    def getWindowRight(self) -> int: ...
    def isUpdateReady(self) -> bool: ...
    def query(self, start_inc: int, end_inc: int, callback: Callable, modify_tracking: bool = True) -> None: ...
    def setVerbose(self, verbose: bool) -> None: ...
    def unload(self) -> None: ...
