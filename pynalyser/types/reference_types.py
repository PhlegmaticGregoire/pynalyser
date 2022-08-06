from typing import TYPE_CHECKING, List, Optional, Tuple

import attr

from .base_types import (AnyType, PynalyserType, SingleType,
                         UnionType, UnknownType)
from .operations import (BINOP_FUNC, BINOP_STR, CMP_FUNC, CMP_STR,
                         DUNDER_BINOP, DUNDER_CMP)
from .op import Signature
from .structure_types import BoolType, IntType, IterableType

if TYPE_CHECKING:
    from ..symbol import Symbol


@attr.s(auto_attribs=True, auto_detect=True)
class SymbolType(PynalyserType):
    name: str
    symbol: "Symbol"

    def deref(self) -> PynalyserType:
        return self.symbol.type.deref()

    def __hash__(self) -> int:
        return hash((type(self), self.name))


def narrow_type(tp: SingleType, both: Tuple[str, str],
                method: str, op_str: str,
                use_left: bool) -> SingleType:

    if use_left:
        this_method = method
        # other_method = "r" + method
        # swapped_cmp_op - lt <=> gt ..
    else:
        this_method = "r" + method
        # other_method = method
        both = both[::-1]

    signature_name = f"__{this_method}__"
    try:
        signature = tp.ops[signature_name].signature
    except KeyError:
        print(type(tp), method, signature_name)
        raise TypeError(
            f"unsupported operand type(s) for {op_str}:"
            f" '{both[0]}' and '{both[1]}'")

    # TODO: also add type that have __{other_method}__ op
    other = UnionType.make(*signature)
    assert isinstance(other, SingleType)

    return other


@attr.s(auto_attribs=True, hash=True)
class BinOpType(PynalyserType):
    op: str
    left: PynalyserType
    right: PynalyserType

    def __attrs_post_init__(self) -> None:
        left = self.left.deref()
        assert isinstance(left, SingleType)
        right = self.right.deref()
        assert isinstance(right, SingleType)

        if not left.is_completed and not right.is_completed:
            raise NotImplementedError
        elif not left.is_completed:
            left = narrow_type(
                right, (left.name, right.name),
                DUNDER_BINOP[self.op], BINOP_STR[self.op],
                use_left=False)
        elif not right.is_completed:
            right = narrow_type(
                left, (left.name, right.name),
                DUNDER_BINOP[self.op], BINOP_STR[self.op],
                use_left=True)
        # else:
        #     raise NotImplementedError
        #     name = op_to_dunder[op]
        #     lsig = left.dunder_signatures.get(name, None)
        #     if lsig is not None:
        #         if type(right) in lsig:
        #             return getattr(right, name)(left)

        #     name = "r" + name
        #     rsig = right.dunder_signatures.get(name, None)
        #     if rsig is not None:
        #         if type(left) in rsig:
        #             return getattr(left, name)(right)
        #     elif lsig is None:
        #         raise TypeError("")

        if isinstance(self.left, SymbolType):
            self.left.symbol.type = left
        if isinstance(self.right, SymbolType):
            self.right.symbol.type = right

    def deref(self) -> PynalyserType:
        return BINOP_FUNC[self.op](self.left.deref(), self.right.deref())


@attr.s(auto_attribs=True, hash=True)
class CompareType(PynalyserType):
    left: PynalyserType
    ops: List[str]
    comparators: List[PynalyserType]

    def __attrs_post_init__(self) -> None:
        left = self.left.deref()
        assert isinstance(left, SingleType)
        right = self.comparators[0].deref()
        assert isinstance(right, SingleType)

        if not left.is_completed and not right.is_completed:
            pass
            # raise NotImplementedError
        elif not left.is_completed:
            left = narrow_type(
                right, (left.name, right.name),
                DUNDER_CMP[self.ops[0]], CMP_STR[self.ops[0]],
                use_left=False)
        elif not right.is_completed:
            right = narrow_type(
                left, (left.name, right.name),
                DUNDER_CMP[self.ops[0]], CMP_STR[self.ops[0]],
                use_left=True)

        if isinstance(self.left, SymbolType):
            self.left.symbol.type = left
        if isinstance(self.comparators[0], SymbolType):
            self.comparators[0].symbol.type = right

    def deref(self) -> PynalyserType:
        return BoolType()  # or exception raised


@attr.s(auto_attribs=True, hash=True)
class SubscriptType(PynalyserType):
    value: PynalyserType
    slice: PynalyserType

    def deref(self) -> PynalyserType:
        return self.value.deref()[self.slice.deref()]  # type: ignore

    # def visit_Subscript(self, node: ast.Subscript) -> PynalyserType:
    #     value_type = self.visit(node.value)
    #     slice_type = self.visit(node.slice)
    #     if isinstance(value_type, SequenceType):
    #         return value_type[slice_type]

    #     raise NotImplementedError


@attr.s(auto_attribs=True, hash=True)
class ItemType(PynalyserType):
    iterable: PynalyserType

    def __attrs_post_init__(self) -> None:
        tp = self.iterable.deref()
        if tp is UnknownType:
            if isinstance(self.iterable, SymbolType):
                self.iterable.symbol.type = IterableType(
                    item_type=UnknownType, is_builtin=False)
            # XXX: should we let it be and cause an error?
            # else:
            #     self.iterable = IterableType(
            #         item_type=UnknownType, is_builtin=False)

    def deref(self) -> PynalyserType:
        return self.iterable.deref().item_type.deref()  # type: ignore


@attr.s(auto_attribs=True, hash=True)
class CallType(PynalyserType):
    func: PynalyserType
    args: Tuple[PynalyserType, ...]
    keywords: Tuple[Tuple[Optional[str], PynalyserType], ...]

    def deref(self) -> PynalyserType:
        if isinstance(self.func, SymbolType) and self.func.name == "range":
            return IterableType(item_type=IntType(),
                                is_builtin=False)  # XXX: is_builtin??

        return AnyType
