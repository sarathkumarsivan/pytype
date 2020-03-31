"""Tests for the analysis phase matcher (match_var_against_type)."""

from pytype import file_utils
from pytype.tests import test_base


class MatchTest(test_base.TargetPython3BasicTest):
  """Tests for matching types."""

  def testNoArgumentPyTDFunctionAgainstCallable(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def bar() -> bool
      """)
      _, errors = self.InferWithErrors("""\
        from typing import Callable
        import foo

        def f(x: Callable[[], int]): ...
        def g(x: Callable[[], str]): ...

        f(foo.bar)  # ok
        g(foo.bar)  # wrong-arg-types[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {
          "e": r"\(x: Callable\[\[\], str\]\).*\(x: Callable\[\[\], bool\]\)"})

  def testPyTDFunctionAgainstCallableWithTypeParameters(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f1(x: int) -> int: ...
        def f2(x: int) -> bool: ...
        def f3(x: int) -> str: ...
      """)
      _, errors = self.InferWithErrors("""\
        from typing import Callable, TypeVar
        import foo

        T_plain = TypeVar("T_plain")
        T_constrained = TypeVar("T_constrained", int, bool)
        def f1(x: Callable[[T_plain], T_plain]): ...
        def f2(x: Callable[[T_constrained], T_constrained]): ...

        f1(foo.f1)  # ok
        f1(foo.f2)  # ok
        f1(foo.f3)  # wrong-arg-types[e1]
        f2(foo.f1)  # ok
        f2(foo.f2)  # wrong-arg-types[e2]
        f2(foo.f3)  # wrong-arg-types[e3]
      """, pythonpath=[d.path])
      expected = r"Callable\[\[Union\[bool, int\]\], Union\[bool, int\]\]"
      self.assertErrorRegexes(errors, {
          "e1": (r"Expected.*Callable\[\[str\], str\].*"
                 r"Actual.*Callable\[\[int\], str\]"),
          "e2": (r"Expected.*Callable\[\[bool\], bool\].*"
                 r"Actual.*Callable\[\[int\], bool\]"),
          "e3": (r"Expected.*" + expected + ".*"
                 r"Actual.*Callable\[\[int\], str\]")})

  def testInterpreterFunctionAgainstCallable(self):
    _, errors = self.InferWithErrors("""\
      from typing import Callable
      def f(x: Callable[[bool], int]): ...
      def g1(x: int) -> bool:
        return __any_object__
      def g2(x: str) -> int:
        return __any_object__
      f(g1)  # ok
      f(g2)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": (r"Expected.*Callable\[\[bool\], int\].*"
              r"Actual.*Callable\[\[str\], int\]")})

  def testBoundInterpreterFunctionAgainstCallable(self):
    _, errors = self.InferWithErrors("""\
      from typing import Callable

      class A(object):
        def f(self, x: int) -> bool:
          return __any_object__
      unbound = A.f
      bound = A().f

      def f1(x: Callable[[bool], int]): ...
      def f2(x: Callable[[A, bool], int]): ...
      def f3(x: Callable[[bool], str]): ...

      f1(bound)  # ok
      f2(bound)  # wrong-arg-types[e1]
      f3(bound)  # wrong-arg-types[e2]
      f1(unbound)  # wrong-arg-types[e3]
      f2(unbound)  # ok
    """)
    self.assertErrorRegexes(errors, {
        "e1": (r"Expected.*Callable\[\[A, bool\], int\].*"
               r"Actual.*Callable\[\[int\], bool\]"),
        "e2": (r"Expected.*Callable\[\[bool\], str\].*"
               r"Actual.*Callable\[\[int\], bool\]"),
        "e3": (r"Expected.*Callable\[\[bool\], int\].*"
               r"Actual.*Callable\[\[Any, int\], bool\]")})

  def testCallableParameters(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any, Callable, List, TypeVar
        T = TypeVar("T")
        def f1(x: Callable[..., T]) -> List[T]: ...
        def f2(x: Callable[[T], Any]) -> List[T]: ...
      """)
      ty = self.Infer("""\
        from typing import Any, Callable
        import foo

        def g1(): pass
        def g2() -> int: pass
        v1 = foo.f1(g1)
        v2 = foo.f1(g2)

        def g3(x): pass
        def g4(x: int): pass
        w1 = foo.f2(g3)
        w2 = foo.f2(g4)
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, List
        foo = ...  # type: module
        def g1() -> Any: ...
        def g2() -> int: ...
        def g3(x) -> Any: ...
        def g4(x: int) -> Any: ...

        v1 = ...  # type: list
        v2 = ...  # type: List[int]
        w1 = ...  # type: list
        w2 = ...  # type: List[int]
      """)

  def testVariableLengthFunctionAgainstCallable(self):
    _, errors = self.InferWithErrors("""\
      from typing import Any, Callable
      def f(x: Callable[[int], Any]): pass
      def g1(x: int=0): pass
      def g2(x: str=""): pass
      f(g1)  # ok
      f(g2)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": (r"Expected.*Callable\[\[int\], Any\].*"
              r"Actual.*Callable\[\[str\], Any\]")})

  def testCallableInstanceAgainstCallableWithTypeParameters(self):
    _, errors = self.InferWithErrors("""\
      from typing import Callable, TypeVar
      T = TypeVar("T")
      def f(x: Callable[[T], T]): ...
      def g() -> Callable[[int], str]: return __any_object__
      f(g())  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": (r"Expected.*Callable\[\[str\], str\].*"
              r"Actual.*Callable\[\[int\], str\]")})

  def testFunctionWithTypeParameterReturnAgainstCallable(self):
    self.InferWithErrors("""\
      from typing import Callable, AnyStr, TypeVar
      T = TypeVar("T")
      def f(x: Callable[..., AnyStr]): ...
      def g1(x: AnyStr) -> AnyStr: return x
      def g2(x: T) -> T: return x

      f(g1)  # ok
      f(g2)  # wrong-arg-types
    """)

  def testUnionInTypeParameter(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Callable, Iterator, List, TypeVar
        T = TypeVar("T")
        def decorate(func: Callable[..., Iterator[T]]) -> List[T]
      """)
      ty = self.Infer("""
        from typing import Generator, Optional
        import foo
        @foo.decorate
        def f() -> Generator[Optional[str], None, None]:
          yield "hello world"
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List, Optional
        foo = ...  # type: module
        f = ...  # type: List[Optional[str]]
      """)

  def testAnyStr(self):
    self.Check("""
      from typing import AnyStr, Dict, Tuple
      class Foo(object):
        def bar(self, x: Dict[Tuple[AnyStr], AnyStr]): ...
    """)

  def testFormalType(self):
    self.InferWithErrors("""\
      from typing import AnyStr, List, NamedTuple
      def f(x: str):
        pass
      f(AnyStr)  # invalid-typevar
      def g(x: List[str]):
        pass
      g([AnyStr])  # invalid-typevar
      H = NamedTuple("H", [('a', AnyStr)])  # invalid-typevar
    """)

  def testTypeVarWithBound(self):
    _, errors = self.InferWithErrors("""\
      from typing import Callable, TypeVar
      T1 = TypeVar("T1", bound=int)
      T2 = TypeVar("T2")
      def f(x: T1) -> T1:
        return __any_object__
      def g(x: Callable[[T2], T2]) -> None:
        pass
      g(f)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Expected.*T2.*Actual.*T1"})

  def testCallableBaseClass(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Callable, Union, Type
        def f() -> Union[Callable[[], ...], Type[Exception]]
        def g() -> Union[Type[Exception], Callable[[], ...]]
      """)
      self.Check("""
        from typing import Union
        import foo
        class Foo(foo.f()):
          pass
        class Bar(foo.g()):
          pass
        def f(x: Foo, y: Bar) -> Union[Bar, Foo]:
          return x or y
        f(Foo(), Bar())
      """, pythonpath=[d.path])

  def testAnyStrAgainstCallable(self):
    # Because `T` appears only once in the callable, it does not do any
    # intra-callable type enforcement, so AnyStr is allowed to match it.
    self.Check("""
      from typing import Any, AnyStr, Callable, TypeVar
      T = TypeVar('T')
      def f(x: AnyStr) -> AnyStr:
        return x
      def g(f: Callable[[T], Any], x: T):
        pass
      g(f, 'hello')
    """)

  def testAnyStrAgainstBoundedCallable(self):
    # Constraints and bounds should still be enforced when a type parameter
    # appears only once in a callable.
    errors = self.CheckWithErrors("""\
      from typing import Any, AnyStr, Callable, TypeVar
      IntVar = TypeVar('IntVar', bound=int)
      def f(x: AnyStr) -> AnyStr:
        return x
      def g(f: Callable[[IntVar], Any], x: IntVar):
        pass
      g(f, 0)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"Callable\[\[IntVar\], Any\].*Callable\[\[AnyStr\], AnyStr\]"})

  def testAnyStrAgainstMultipleParamCallable(self):
    # Callable[[T], T] needs to accept any argument, so AnyStr cannot match it.
    errors = self.CheckWithErrors("""\
      from typing import Any, AnyStr, Callable, TypeVar
      T = TypeVar('T')
      def f(x: AnyStr) -> AnyStr:
        return x
      def g(f: Callable[[T], T]):
        pass
      g(f)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"Callable\[\[T\], T\].*Callable\[\[AnyStr\], AnyStr\]"})


class MatchTestPy3(test_base.TargetPython3FeatureTest):
  """Tests for matching types."""

  # Forked into py2 and py3 versions

  def testCallable(self):
    ty = self.Infer("""
      import tokenize
      def f():
        pass
      x = tokenize.generate_tokens(f)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generator
      tokenize = ...  # type: module
      def f() -> NoneType
      x = ...  # type: Generator[tokenize.TokenInfo, None, None]
    """)

  def testCallableAgainstGeneric(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import TypeVar, Callable, Generic, Iterable, Iterator
        A = TypeVar("A")
        N = TypeVar("N")
        class Foo(Generic[A]):
          def __init__(self, c: Callable[[], N]):
            self = Foo[N]
        x = ...  # type: Iterator[int]
      """)
      self.Check("""
        import foo
        foo.Foo(foo.x.__next__)
      """, pythonpath=[d.path])

  def testEmpty(self):
    ty = self.Infer("""
      a = []
      b = ["%d" % i for i in a]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      a = ...  # type: List[nothing]
      b = ...  # type: List[str]
    """)

  def testBoundAgainstCallable(self):
    ty = self.Infer("""
      import io
      import tokenize
      x = tokenize.generate_tokens(io.StringIO("").readline)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generator
      io = ...  # type: module
      tokenize = ...  # type: module
      x = ...  # type: Generator[tokenize.TokenInfo, None, None]
    """)


test_base.main(globals(), __name__ == "__main__")
