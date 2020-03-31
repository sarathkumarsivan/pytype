"""Tests of builtins (in pytd/builtins/{version}/__builtins__.pytd).

File 3/3. Split into parts to enable better test parallelism.
"""


from pytype import abstract_utils
from pytype import file_utils
from pytype.tests import test_base


class BuiltinTests3(test_base.TargetIndependentTest):
  """Tests for builtin methods and classes."""

  def testSuperAttribute(self):
    ty = self.Infer("""
      x = super.__name__
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: str
    """)

  def testSlice(self):
    ty = self.Infer("""
      x1 = [1,2,3][1:None]
      x2 = [1,2,3][None:2]
      x3 = [1,2,3][None:None]
      x4 = [1,2,3][1:3:None]
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      x1 = ...  # type: List[int]
      x2 = ...  # type: List[int]
      x3 = ...  # type: List[int]
      x4 = ...  # type: List[int]
    """)

  def testSliceAttributes(self):
    ty = self.Infer("""
      v = slice(1)
      start = v.start
      stop = v.stop
      step = v.step
      indices = v.indices(0)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional, Tuple
      v = ...  # type: slice
      start = ...  # type: Optional[int]
      stop = ...  # type: Optional[int]
      step = ...  # type: Optional[int]
      indices = ...  # type: Tuple[int, int, int]
    """)

  def testNextFunction(self):
    ty = self.Infer("""
      a = next(iter([1, 2, 3]))
      b = next(iter([1, 2, 3]), default = 4)
      c = next(iter([1, 2, 3]), "hello")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      a = ...  # type: int
      b = ...  # type: int
      c = ...  # type: Union[int, str]
    """)

  def testImplicitTypeVarImport(self):
    ty, _ = self.InferWithErrors("""\
      v = %s  # name-error
    """ % abstract_utils.T)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      v = ...  # type: Any
    """)

  def testExplicitTypeVarImport(self):
    self.Check("""
      from __builtin__ import _T
      _T
    """)

  def testClassOfType(self):
    ty = self.Infer("""
      v = int.__class__
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      v = ...  # type: Type[type]
    """)

  @test_base.skip("broken")
  def testClear(self):
    ty = self.Infer("""\
      x = {1, 2}
      x.clear()
      y = {"foo": 1}
      y.clear()
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Set
      x = ...  # type: Set[nothing]
      y = ...  # type: Dict[nothing, nothing]
    """)

  def testCmp(self):
    ty = self.Infer("""
      if not cmp(4, 4):
        x = 42
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: int
    """)

  def testRepr(self):
    ty = self.Infer("""
      if repr("hello world"):
        x = 42
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: int
    """)

  def testIntInit(self):
    _, errors = self.InferWithErrors("""\
      int()
      int(0)
      int("0")
      int("0", 10)
      int(u"0")
      int(u"0", 10)
      int(0, 1, 2)  # wrong-arg-count[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"1.*4"})

  def testNewlines(self):
    with file_utils.Tempdir() as d:
      # pylint: disable=g-backslash-continuation
      d.create_file("newlines.txt", """\
          1
          2
          3
          """)
      self.Check("""\
          l = []
          with open("newlines.txt", "rU") as f:
            for line in f:
              l.append(line)
            newlines = f.newlines
          """)

  def testInitWithUnicode(self):
    self.Check("""
        int(u"123.0")
        float(u"123.0")
        complex(u"123.0")
    """)

  def testIOWrite(self):
    self.Check("""
        import sys
        sys.stdout.write("hello world")
    """)

  def testBinaryIOWrite(self):
    self.Check("""
      with open('foo', 'wb') as f:
        f.write(bytearray([1, 2, 3]))
    """)

  def testHasAttrNone(self):
    self.assertNoCrash(self.Check, "hasattr(int, None)")

  def testNumberAttrs(self):
    ty = self.Infer("""\
      a = (42).denominator
      b = (42).numerator
      c = (42).real
      d = (42).imag
      e = (3.14).conjugate()
      f = (3.14).is_integer()
      g = (3.14).real
      h = (3.14).imag
      i = (2j).conjugate()
      j = (2j).real
      k = (2j).imag
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      a = ...  # type: int
      b = ...  # type: int
      c = ...  # type: int
      d = ...  # type: int
      e = ...  # type: float
      f = ...  # type: bool
      g = ...  # type: float
      h = ...  # type: float
      i = ...  # type: complex
      j = ...  # type: float
      k = ...  # type: float
    """)

  def testBuiltins(self):
    # This module doesn't exist, on Python 2. However, it exists in typeshed, so
    # make sure that we don't break (report pyi-error) when we import it.
    self.Check("""
      import builtins  # pytype: disable=import-error
    """)

  def testSpecialBuiltinTypes(self):
    self.InferWithErrors("""\
      isinstance(1, int)
      isinstance(1, "no")  # wrong-arg-types
      issubclass(int, object)
      issubclass(0, 0)  # wrong-arg-types
      issubclass(int, 0)  # wrong-arg-types
      hasattr(str, "upper")
      hasattr(int, int)  # wrong-arg-types
      """)

  def testUnpackList(self):
    ty = self.Infer("""
      x = [1, ""]
      a, b = x
      x.append(2)
      c, d, e = x
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: list[int or str]
      a = ...  # type: int
      b = ...  # type: str
      c = ...  # type: int or str
      d = ...  # type: int or str
      e = ...  # type: int or str
    """)

  def testBytearraySetItem(self):
    self.Check("""
      ba = bytearray(b"hello")
      ba[0] = 106
      ba[4:] = [121, 102, 105, 115, 104]
      ba[4:] = b"yfish"
      ba[4:] = bytearray("yfish")
      ba[:5] = b""
      ba[1:2] = b"la"
      ba[2:3:2] = b"u"
    """)

  def testBytearraySetItemPy3(self):
    self.Check("""
      ba = bytearray(b"hello")
      ba[0] = 106
      ba[:1] = [106]
      ba[:1] = b"j"
      ba[:1] = bytearray(b"j")
      ba[:1] = memoryview(b"j")
      ba[4:] = b"yfish"
      ba[0:5] = b""
      ba[1:4:2] = b"at"
    """)

  def testFromHex(self):
    ty = self.Infer("""
      f1 = float.fromhex(b"feed")
      f2 = float.fromhex(bytearray(b"feed"))
      b1 = bytearray.fromhex(b"beef")
      b2 = bytearray.fromhex(bytearray("beef"))
    """)
    self.assertTypesMatchPytd(ty, """
      f1 = ...  # type: float
      f2 = ...  # type: float
      b1 = ...  # type: bytearray
      b2 = ...  # type: bytearray
    """)

  def testNoneLength(self):
    errors = self.CheckWithErrors("len(None)  # wrong-arg-types[e]")
    self.assertErrorRegexes(errors, {"e": r"Sized.*None"})

  def testSequenceLength(self):
    self.Check("""
      len("")
      len(u"")
      len(bytearray())
      len([])
      len(())
      len(frozenset())
      len(range(0))
    """)

  def testMappingLength(self):
    self.Check("""
      len({})
    """)

  def testPrintBareType(self):
    ty = self.Infer("""
      from typing import Any, Dict, Type
      d1 = {}  # type: Dict[str, type]
      d2 = {}  # type: Dict[str, Type[Any]]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      d1 = ...  # type: Dict[str, type]
      d2 = ...  # type: Dict[str, type]
    """)

  def testGetFunctionAttr(self):
    self.Check("getattr(lambda: None, '__defaults__')")

  def testStrStartswith(self):
    self.Check("""
      s = "some str"
      s.startswith("s")
      s.startswith(("s", "t"))
      s.startswith("a", start=1, end=2)
    """)

  def testStrEndswith(self):
    self.Check("""
      s = "some str"
      s.endswith("r")
      s.endswith(("r", "t"))
      s.endswith("a", start=1, end=2)
    """)

  def testPath(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/__init__.py")
      self.Check("""
        import foo
        __path__, foo.__path__
      """, pythonpath=[d.path])

  def testDelByteArraySlice(self):
    self.Check("""
      ba = bytearray(b"hello")
      del ba[0:2]
    """)

  def testInput(self):
    self.Check("""
      input()
      input('input: ')
    """)

  def testSetDefaultError(self):
    ty, errors = self.InferWithErrors("""\
      x = {}
      y = x.setdefault()  # wrong-arg-count[e1]
      z = x.setdefault(1, 2, 3, *[])  # wrong-arg-count[e2]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict
      x = ...  # type: Dict[nothing, nothing]
      y = ...  # type: Any
      z = ...  # type: Any
    """)
    self.assertErrorRegexes(errors, {"e1": r"2.*0", "e2": r"2.*3"})

  def testTuple(self):
    ty = self.Infer("""
      def f(x, y):
        return y
      def g():
        args = (4, )
        return f(3, *args)
      g()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar
      _T1 = TypeVar("_T1")
      def f(x, y: _T1) -> _T1: ...
      def g() -> int: ...
    """)


test_base.main(globals(), __name__ == "__main__")
