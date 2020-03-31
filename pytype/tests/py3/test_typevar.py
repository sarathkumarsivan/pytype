"""Tests for TypeVar."""

from pytype import file_utils
from pytype.tests import test_base


class TypeVarTest(test_base.TargetPython3BasicTest):
  """Tests for TypeVar."""

  def testId(self):
    ty = self.Infer("""
      import typing
      T = typing.TypeVar("T")
      def f(x: T) -> T:
        return __any_object__
      v = f(42)
      w = f("")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      typing = ...  # type: module
      T = TypeVar("T")
      def f(x: T) -> T: ...
      v = ...  # type: int
      w = ...  # type: str
    """)
    self.assertTrue(ty.Lookup("f").signatures[0].template)

  def testExtractItem(self):
    ty = self.Infer("""
      from typing import List, TypeVar
      S = TypeVar("S")  # unused
      T = TypeVar("T")
      def f(x: List[T]) -> T:
        return __any_object__
      v = f(["hello world"])
      w = f([True])
    """)
    self.assertTypesMatchPytd(ty, """
      S = TypeVar("S")
      T = TypeVar("T")
      def f(x: typing.List[T]) -> T: ...
      v = ...  # type: str
      w = ...  # type: bool
    """)
    self.assertTrue(ty.Lookup("f").signatures[0].template)

  def testWrapItem(self):
    ty = self.Infer("""
      from typing import List, TypeVar
      T = TypeVar("T")
      def f(x: T) -> List[T]:
        return __any_object__
      v = f(True)
      w = f(3.14)
    """)
    self.assertTypesMatchPytd(ty, """
      T = TypeVar("T")
      def f(x: T) -> typing.List[T]: ...
      v = ...  # type: typing.List[bool]
      w = ...  # type: typing.List[float]
    """)

  def testImportTypeVarNameChange(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        X = TypeVar("X")
      """)
      _, errors = self.InferWithErrors("""
        # This is illegal: A TypeVar("T") needs to be stored under the name "T".
        from a import T as T2  # invalid-typevar[e1]
        from a import X
        Y = X  # invalid-typevar[e2]
        def f(x: T2) -> T2: ...
      """, pythonpath=[d.path])
    self.assertErrorRegexes(errors, {"e1": r"T.*T2", "e2": r"X.*Y"})

  def testMultipleSubstitution(self):
    ty = self.Infer("""
      from typing import Dict, Tuple, TypeVar
      K = TypeVar("K")
      V = TypeVar("V")
      def f(x: Dict[K, V]) -> Tuple[V, K]:
        return __any_object__
      v = f({})
      w = f({"test": 42})
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, Tuple, TypeVar
      K = TypeVar("K")
      V = TypeVar("V")
      def f(x: Dict[K, V]) -> Tuple[V, K]: ...
      v = ...  # type: Tuple[Any, Any]
      w = ...  # type: Tuple[int, str]
    """)

  def testUnion(self):
    ty = self.Infer("""
      from typing import TypeVar, Union
      S = TypeVar("S")
      T = TypeVar("T")
      def f(x: S, y: T) -> Union[S, T]:
        return __any_object__
      v = f("", 42)
      w = f(3.14, False)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar, Union
      S = TypeVar("S")
      T = TypeVar("T")
      def f(x: S, y: T) -> Union[S, T]: ...
      v = ...  # type: Union[str, int]
      w = ...  # type: Union[float, bool]
    """)

  def testBadSubstitution(self):
    _, errors = self.InferWithErrors("""
      from typing import List, TypeVar
      S = TypeVar("S")
      T = TypeVar("T")
      def f1(x: S) -> List[S]:
        return {x}  # bad-return-type[e1]
      def f2(x: S) -> S:
        return 42  # no error because never called
      def f3(x: S) -> S:
        return 42  # bad-return-type[e2]  # bad-return-type[e3]
      def f4(x: S, y: T, z: T) -> List[S]:
        return [y]  # bad-return-type[e4]
      f3("")
      f3(16)  # ok
      f3(False)
      f4(True, 3.14, 0)
      f4("hello", "world", "domination")  # ok
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"List\[S\].*set", "e2": r"str.*int", "e3": r"bool.*int",
        "e4": r"List\[bool\].*List\[Union\[float, int\]\]"})

  def testUseConstraints(self):
    ty, errors = self.InferWithErrors("""
      from typing import TypeVar
      T = TypeVar("T", int, float)
      def f(x: T) -> T:
        return __any_object__
      v = f("")  # wrong-arg-types[e]
      w = f(True)  # ok
      u = f(__any_object__)  # ok
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar
      T = TypeVar("T", int, float)
      def f(x: T) -> T: ...
      v = ...  # type: Any
      w = ...  # type: bool
      u = ...  # type: int or float
    """)
    self.assertErrorRegexes(errors, {"e": r"Union\[float, int\].*str"})

  def testTypeParameterType(self):
    ty = self.Infer("""
      from typing import Type, TypeVar
      T = TypeVar("T")
      def f(x: Type[T]) -> T:
        return __any_object__
      v = f(int)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type, TypeVar
      T = TypeVar("T")
      def f(x: Type[T]) -> T: ...
      v = ...  # type: int
    """)

  def testPrintNestedTypeParameter(self):
    _, errors = self.InferWithErrors("""
      from typing import List, TypeVar
      T = TypeVar("T", int, float)
      def f(x: List[T]): ...
      f([""])  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"List\[Union\[float, int\]\].*List\[str\]"})

  def testConstraintSubtyping(self):
    _, errors = self.InferWithErrors("""
      from typing import TypeVar
      T = TypeVar("T", int, float)
      def f(x: T, y: T): ...
      f(True, False)  # ok
      f(True, 42)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Expected.*y: bool.*Actual.*y: int"})

  def testFilterValue(self):
    _, errors = self.InferWithErrors("""
      from typing import TypeVar
      T = TypeVar("T", int, float)
      def f(x: T, y: T): ...
      x = 3
      x = 42.0
      f(x, 3)  # wrong-arg-types[e]
      f(x, 42.0)  # ok
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Expected.*y: float.*Actual.*y: int"})

  def testFilterClass(self):
    self.Check("""
      from typing import TypeVar
      class A(object): pass
      class B(object): pass
      T = TypeVar("T", A, B)
      def f(x: T, y: T): ...
      x = A()
      x.__class__ = B
      # Setting __class__ makes the type ambiguous to pytype.
      f(x, A())
      f(x, B())
    """)

  def testSplit(self):
    ty = self.Infer("""
      from typing import TypeVar
      T = TypeVar("T", int, type(None))
      def f(x: T) -> T:
        return __any_object__
      if __random__:
        x = None
      else:
        x = 3
      v = id(x) if x else 42
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      import types
      from typing import Optional, TypeVar
      v = ...  # type: int
      x = ...  # type: Optional[int]
      T = TypeVar("T", int, None)
      def f(x: T) -> T: ...
    """)

  def testEnforceNonConstrainedTypeVar(self):
    _, errors = self.InferWithErrors("""
      from typing import TypeVar
      T = TypeVar("T")
      def f(x: T, y: T): ...
      f(42, True)  # ok
      f(42, "")  # wrong-arg-types[e1]
      f(42, 16j)  # ok
      f(object(), 42)  # ok
      f(42, object())  # ok
      f(42.0, "")  # wrong-arg-types[e2]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Expected.*y: int.*Actual.*y: str",
        "e2": r"Expected.*y: float.*Actual.*y: str"})

  def testUselessTypeVar(self):
    self.InferWithErrors("""
      from typing import Tuple, TypeVar
      T = TypeVar("T")
      S = TypeVar("S", int, float)
      def f1(x: T): ...  # invalid-annotation
      def f2() -> T: ...  # invalid-annotation
      def f3(x: Tuple[T]): ...  # invalid-annotation
      def f4(x: Tuple[T, T]): ...  # ok
      def f5(x: S): ...  # ok
      def f6(x: "U"): ...  # invalid-annotation
      def f7(x: T, y: "T"): ...  # ok
      def f8(x: "U") -> "U": ...  # ok
      U = TypeVar("U")
    """)

  def testUseBound(self):
    ty, errors = self.InferWithErrors("""
      from typing import TypeVar
      T = TypeVar("T", bound=float)
      def f(x: T) -> T:
        return x
      v1 = f(__any_object__)  # ok
      v2 = f(True)  # ok
      v3 = f(42)  # ok
      v4 = f(3.14)  # ok
      v5 = f("")  # wrong-arg-types[e]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar
      T = TypeVar("T", bound=float)
      def f(x: T) -> T
      v1 = ...  # type: float
      v2 = ...  # type: bool
      v3 = ...  # type: int
      v4 = ...  # type: float
      v5 = ...  # type: Any
    """)
    self.assertErrorRegexes(errors, {"e": r"x: float.*x: str"})

  def testBadReturn(self):
    self.assertNoCrash(self.Check, """
      from typing import AnyStr, Dict

      class Foo(object):
        def f(self) -> AnyStr: return __any_object__
        def g(self) -> Dict[AnyStr, Dict[AnyStr, AnyStr]]:
          return {'foo': {'bar': self.f()}}
    """)

  def testOptionalTypeVar(self):
    _, errors = self.InferWithErrors("""
      from typing import Optional, TypeVar
      T = TypeVar("T", bound=str)
      def f() -> Optional[T]:
        return 42 if __random__ else None  # bad-return-type[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"Optional\[T\].*int"})

  def testUnicodeLiterals(self):
    ty = self.Infer("""
      from __future__ import unicode_literals
      import typing
      T = typing.TypeVar("T")
      def f(x: T) -> T:
        return __any_object__
      v = f(42)
    """)
    self.assertTypesMatchPytd(ty, """
      import __future__
      from typing import Any
      typing = ...  # type: module
      unicode_literals = ...  # type: __future__._Feature
      T = TypeVar("T")
      def f(x: T) -> T: ...
      v = ...  # type: int
    """)

  def testAnyAsBound(self):
    self.Check("""
      from typing import Any, TypeVar
      T = TypeVar("T", bound=Any)
      def f(x: T) -> T:
        return x
      f(42)
    """)

  def testAnyAsConstraint(self):
    self.Check("""
      from typing import Any, TypeVar
      T = TypeVar("T", str, Any)
      def f(x: T) -> T:
        return x
      f(42)
    """)

  def testNameReuse(self):
    self.Check("""
      from typing import Generic, TypeVar
      T = TypeVar("T", int, float)
      class Foo(Generic[T]):
        def __init__(self, x: T):
          self.x = x
      def f(foo: Foo[T]) -> T:
        return foo.x
    """)

  def testPropertyTypeParam(self):
    # We should allow property signatures of the form f(self) -> X[T] without
    # needing to annotate 'self' if the class is generic and we use its type
    # parameter in the property's signature.
    ty = self.Infer("""
      from typing import TypeVar, Generic
      T = TypeVar('T')
      class A(Generic[T]):
          def __init__(self, foo: T):
              self._foo = foo
          @property
          def foo(self) -> T:
              return self._foo
          @foo.setter
          def foo(self, foo: T) -> None:
              self._foo = foo
    """)
    # types inferred as Any due to b/123835298
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar, Generic, Any
      T = TypeVar('T')
      class A(Generic[T]):
          _foo: Any
          foo: Any
          def __init__(self, foo: T) -> None
    """)


class TypeVarTestPy3(test_base.TargetPython3FeatureTest):
  """Tests for TypeVar in Python 3."""

  def testUseConstraintsFromPyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import AnyStr, TypeVar
        T = TypeVar("T", int, float)
        def f(x: T) -> T: ...
        def g(x: AnyStr) -> AnyStr: ...
      """)
      _, errors = self.InferWithErrors("""
        import foo
        foo.f("")  # wrong-arg-types[e1]
        foo.g(0)  # wrong-arg-types[e2]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {
          "e1": r"Union\[float, int\].*str",
          "e2": r"Union\[bytes, str\].*int"})

  def testSubprocess(self):
    ty = self.Infer("""
      import subprocess
      from typing import List
      def run(args: List[str]):
        result = subprocess.run(
          args,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE,
          universal_newlines=True)
        if result.returncode:
          raise subprocess.CalledProcessError(
              result.returncode, args, result.stdout)
        return result.stdout
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      subprocess: module
      def run(args: List[str]) -> str
    """)

  def testAbstractClassmethod(self):
    self.Check("""
      from abc import ABC, abstractmethod
      from typing import Type, TypeVar

      T = TypeVar('T', bound='Foo')

      class Foo(ABC):
        @classmethod
        @abstractmethod
        def f(cls: Type[T]) -> T:
          return cls()
    """)


test_base.main(globals(), __name__ == "__main__")
