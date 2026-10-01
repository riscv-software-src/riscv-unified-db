# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Source-only lowering of accepted IDL ASTs to the retained hart macro ABI.

All inference, evaluation and pruning belong to the ordinary compiler/passes.
This consumer only chooses native representations and writes C++.
"""

from __future__ import annotations

from udb.idl import ast
from udb.idl.errors import IdlValueUnknown
from udb.idl.passes import constexpr
from udb.idl.symbols import SymbolTable, Var
from udb.idl.types import WIDTH_UNKNOWN, RegFileElementType, TypeKind

from .types import CppGenerationError, cpp_type, literal


class Emitter:
    def __init__(self, symtab: SymbolTable):
        self.symtab = symtab.deep_clone()

    def known(self, node: ast.Node):
        return node.value(self.symtab)

    def runtime_width(self, dtype, *, raw=False):
        if dtype.width_ast is None:
            return "BitsInfinitePrecision"
        width = self.expression(dtype.width_ast)
        return width if raw else f"{width}.get()"

    def width(self, node: ast.Node) -> str:
        try:
            return str(self.known(node))
        except IdlValueUnknown:
            return self.expression(node) + ".get()"

    def type_name(self, node: ast.Node) -> str:
        if isinstance(node, ast.UserTypeName):
            dtype = node.type(self.symtab)
            return f"__UDB_STRUCT({node.name})" if dtype.kind is TypeKind.STRUCT else node.name
        if isinstance(node, ast.BuiltinTypeName):
            if node.type_name == "XReg":
                return f"PossiblyUnknownBits<{max(self.symtab.possible_xlens)}>"
            if node.type_name in {"U32", "U64"}:
                return f"PossiblyUnknownBits<{node.type_name[1:]}>"
            if node.type_name == "Bits":
                dtype = node.type(self.symtab)
                try:
                    return f"PossiblyUnknownBits<{self.known(node.bits_expression)}>"
                except IdlValueUnknown:
                    if constexpr(node.bits_expression, self.symtab):
                        return f"PossiblyUnknownBits<{self.expression(node.bits_expression)}.get()>"
                    return cpp_type(dtype)
        return cpp_type(node.type(self.symtab))

    def _register(self, node: ast.Node) -> str | None:
        dtype = node.type(self.symtab)
        if (
            dtype.kind is TypeKind.ARRAY
            and isinstance(dtype.sub_type, RegFileElementType)
            and dtype.is_global
        ):
            return dtype.sub_type.name.lower()
        return None

    def _csr(self, node: ast.Node) -> str:
        csr = node.csr_def(self.symtab)
        if csr is not None:
            return f"__UDB_CSR_BY_NAME({csr.name.replace('.', '_')})"
        if isinstance(node, ast.CsrWrite):
            return f"__UDB_CSR_BY_ADDR(({self.expression(node.idx)}))"
        raise CppGenerationError(f"{node.source.label}: unresolved CSR {node.text}")

    def expression(self, node: ast.Node) -> str:
        emit = self.expression
        if isinstance(node, ast.Noop):
            return ""
        if isinstance(node, ast.IntLiteral):
            dtype = node.type(self.symtab)
            value = node.value(self.symtab)
            signed = str(dtype.is_signed).lower()
            width = dtype.width
            runtime = width == WIDTH_UNKNOWN
            if runtime:
                width = max(self.symtab.possible_xlens)
            family = "_RuntimeBits" if runtime else "_Bits"
            if isinstance(value, ast.UnknownLiteral):
                family = "_PossiblyUnknownRuntimeBits" if runtime else "_PossiblyUnknownBits"
                text = f'"{value}"_xb'
            else:
                text = f"{value & ((1 << width) - 1)}_b"
            args = text + (", __UDB_XLEN" if runtime else "")
            return f"{family}<{width}, {signed}>{{{args}}}"
        if isinstance(node, ast.StringLiteral):
            return literal(node.content)
        if isinstance(node, (ast.TrueExpression, ast.FalseExpression)):
            return "true" if isinstance(node, ast.TrueExpression) else "false"
        if isinstance(node, (ast.DontCareReturn, ast.DontCareLvalue)):
            return "{}"
        if isinstance(node, ast.BuiltinVariable):
            return {"$pc": "__UDB_PC", "$encoding": "__UDB_ENCODING"}[node.name]
        if isinstance(node, ast.Id):
            binding = self.symtab.get(node.name)
            if isinstance(binding, Var):
                if binding.param:
                    macro = (
                        "__UDB_STATIC_PARAM"
                        if constexpr(node, self.symtab)
                        else "__UDB_RUNTIME_PARAM"
                    )
                    return f"{macro}({node.name})"
                if binding.type.is_global:
                    macro = (
                        "__UDB_CONST_GLOBAL" if binding.type.is_const else "__UDB_MUTABLE_GLOBAL"
                    )
                    return f"{macro}({node.name})"
                if binding.decode_var:
                    return node.name + "()"
            return node.name
        if isinstance(node, (ast.BuiltinTypeName, ast.UserTypeName)):
            return self.type_name(node)
        if isinstance(node, ast.EnumRef):
            return f"{node.class_name}{{{node.class_name}::{node.member_name}}}"
        if isinstance(node, ast.BinaryExpression):
            lhs, rhs = emit(node.lhs), emit(node.rhs)
            if node.op in {">>>", "`+", "`-", "`*"}:
                method = {
                    ">>>": "sra",
                    "`+": "widening_add",
                    "`-": "widening_sub",
                    "`*": "widening_mul",
                }[node.op]
                return f"({lhs}.{method}({rhs}))"
            if node.op == "`<<":
                try:
                    return f"({lhs}.template widening_sll<{self.known(node.rhs)}>())"
                except IdlValueUnknown:
                    return f"({lhs}.widening_sll({rhs}))"
            return f"({lhs} {node.op} {rhs})"
        if isinstance(node, ast.UnaryOperatorExpression):
            return f"{node.op}({emit(node.expression)})"
        if isinstance(node, ast.ParenExpression):
            return f"({emit(node.expression)})"
        if isinstance(node, ast.TernaryOperatorExpression):
            dtype = cpp_type(node.type(self.symtab))
            return f"(({emit(node.condition)}) ? static_cast<{dtype}>({emit(node.true_expression)}) : static_cast<{dtype}>({emit(node.false_expression)}))"
        if isinstance(node, ast.SignCast):
            return f"({emit(node.expression)}).make_signed()"
        if isinstance(node, ast.WidthReveal):
            return f"{emit(node.expression)}.width()"
        if isinstance(node, ast.BitsCast):
            dtype = node.expression.type(self.symtab)
            if dtype.kind is TypeKind.ENUM_REF:
                return f"Bits<{dtype.enum_class.width}>{{{emit(node.expression)}.value()}}"
            return f"{cpp_type(node.type(self.symtab))}({emit(node.expression)})"
        if isinstance(node, ast.EnumCast):
            return f"{node.enum_class_name.name}{{{emit(node.expression)}}}"
        if isinstance(node, (ast.EnumSize, ast.EnumElementSize)):
            return str(self.known(node))
        if isinstance(node, ast.EnumArrayCast):
            dtype = node.enum_class_name.type(self.symtab)
            return (
                f"std::array<Bits<{dtype.width}>, {len(dtype.element_names)}>{{"
                + ", ".join(f"{v}_b" for v in dtype.element_values)
                + "}"
            )
        if isinstance(node, ast.ArrayLiteral):
            subtype = cpp_type(node.children[0].type(self.symtab))
            return (
                f"std::array<{subtype}, {len(node.children)}>{{"
                + ", ".join(map(emit, node.children))
                + "}"
            )
        if isinstance(node, ast.ConcatenationExpression):
            return "concat(" + ", ".join(map(emit, node.children)) + ")"
        if isinstance(node, ast.ReplicationExpression):
            try:
                return f"{emit(node.v)}.template replicate<{self.known(node.n)}>()"
            except IdlValueUnknown:
                return f"{emit(node.v)}.replicate({emit(node.n)})"
        if isinstance(node, ast.ArrayIncludes):
            return f"_array_includes({emit(node.array)}, {emit(node.expression)})"
        if isinstance(node, ast.ArraySize):
            try:
                return f"{len(self.known(node.array))}_b"
            except IdlValueUnknown:
                return f"Bits<sizeof(std::size_t)*8>{{({emit(node.array)}).size()}}"
        if isinstance(node, ast.AryElementAccess):
            rf = self._register(node.var)
            if rf:
                return f"__UDB_HART->_{rf}reg({emit(node.index)})"
            if node.var.type(self.symtab).is_integral:
                try:
                    return f"{emit(node.var)}.template at<{self.known(node.index)}>()"
                except IdlValueUnknown:
                    return f"{emit(node.var)}.at({emit(node.index)})"
            return f"{emit(node.var)}.at({emit(node.index)}.get())"
        if isinstance(node, ast.AryRangeAccess):
            try:
                return f"{emit(node.var)}.template extract<{self.known(node.msb)}, {self.known(node.lsb)}>()"
            except IdlValueUnknown:
                return f"{emit(node.var)}.extract({emit(node.msb)}, {emit(node.lsb)})"
        if isinstance(node, ast.FieldAccessExpression):
            value = f"{emit(node.obj)}.{node.field_name}"
            if node.obj.type(self.symtab).kind is TypeKind.BITFIELD:
                return f"static_cast<PossiblyUnknownBits<{node.type(self.symtab).width}>>({value})"
            return value
        if isinstance(node, (ast.PostIncrementExpression, ast.PostDecrementExpression)):
            return emit(node.rval) + (
                "++" if isinstance(node, ast.PostIncrementExpression) else "--"
            )
        if isinstance(node, ast.CsrFieldReadExpression):
            return f"{self._csr(node.csr)}.{node.field_name}()._hw_read()"
        if isinstance(node, ast.CsrReadExpression):
            csr = node.csr_def(self.symtab)
            dynamic = self.symtab.multi_xlen and self._csr_dynamic(csr)
            return f"{self._csr(node)}._hw_read(" + ("__UDB_XLEN" if dynamic else "") + ")"
        if isinstance(node, ast.CsrFunctionCall):
            target = self._csr(node.csr)
            args = ", ".join(map(emit, node.args))
            function = node.function_name.replace("?", "_Q_")
            csr = node.csr.csr_def(self.symtab)
            if function == "sw_read":
                if csr is None or (self.symtab.multi_xlen and self._csr_dynamic(csr)):
                    args = "__UDB_XLEN"
                function = "_sw_read" if csr is not None else "sw_read"
            elif function == "address" and csr is not None:
                function = "_address"
            return f"{target}.{function}({args})"
        if isinstance(node, ast.FunctionCallExpression):
            args = ", ".join(map(emit, node.args))
            if node.name == "implemented?":
                return f"__UDB_FUNC_CALL template _implemented_Q_<{emit(node.args[0])}>()"
            if node.name == "implemented_version?":
                return f"__UDB_FUNC_CALL template _implemented_version_Q_<{emit(node.args[0])}, {node.args[1].raw_text}>()"
            definition = self.symtab.get(node.name).func_def_ast
            prefix = (
                "__UDB_CONSTEXPR_FUNC_CALL"
                if constexpr(definition, self.symtab)
                else "__UDB_FUNC_CALL"
            )
            return f"{prefix} {node.name.replace('?', '_Q_')}({args})"
        if isinstance(node, ast.PcAssignment):
            return f"__UDB_SET_PC(({emit(node.rhs)}))"
        if isinstance(node, ast.VariableAssignment):
            rhs = self._array_cast(
                node.lhs.type(self.symtab), node.rhs.type(self.symtab), emit(node.rhs)
            )
            return f"{emit(node.lhs)} = {rhs}"
        if isinstance(node, ast.AryElementAssignment):
            rf = self._register(node.lhs)
            if rf:
                return f"__UDB_HART->_set_{rf}reg({emit(node.index)}, {emit(node.rhs)})"
            if node.lhs.type(self.symtab).kind is TypeKind.BITS:
                return f"{emit(node.lhs)}.setBit({emit(node.index)}, {emit(node.rhs)})"
            return f"{emit(node.lhs)}.at({emit(node.index)}.get()) = {emit(node.rhs)}"
        if isinstance(node, ast.AryRangeAssignment):
            return self._range_assignment(node)
        if isinstance(node, ast.FieldAssignment):
            return f"{emit(node.id)}.{node.field_name} = {emit(node.rhs)}"
        if isinstance(node, ast.CsrFieldAssignment):
            field = node.csr_field.field_def(self.symtab)
            dynamic = self.symtab.multi_xlen and self._field_dynamic(field)
            return (
                f"{self._csr(node.csr_field.csr)}.{field.name}()._hw_write({emit(node.write_value)}"
                + (", __UDB_XLEN" if dynamic else "")
                + ")"
            )
        if isinstance(node, ast.CsrSoftwareWrite):
            return f"{self._csr(node.csr)}.sw_write({emit(node.expression)}, __UDB_XLEN)"
        if isinstance(node, ast.MultiVariableAssignment):
            return (
                "std::tie("
                + ", ".join(map(emit, node.variables))
                + f") = {emit(node.function_call)}"
            )
        if isinstance(
            node,
            (
                ast.VariableDeclaration,
                ast.VariableDeclarationWithInitialization,
                ast.MultiVariableDeclaration,
            ),
        ):
            return self._declaration(node)
        raise CppGenerationError(
            f"{node.source.label}:{node.lineno}: Unsupported C++ node {type(node).__name__}: {node.text}"
        )

    @staticmethod
    def _csr_dynamic(csr) -> bool:
        return csr.dynamic_length() or any(
            Emitter._field_dynamic(field) or not field.defined_in_all_bases for field in csr.fields
        )

    @staticmethod
    def _field_dynamic(field) -> bool:
        return field.dynamic_location()

    @staticmethod
    def _array_cast(lhs, rhs, text):
        if lhs.kind is TypeKind.ARRAY and rhs.kind is TypeKind.ARRAY:
            subtype = cpp_type(lhs.sub_type)
            if subtype != cpp_type(rhs.sub_type):
                return f"array_cast<{subtype}>({text})"
        return text

    def _declaration(self, node):
        node.add_symbol(self.symtab)
        dtype = node.type(self.symtab)
        typ = self.type_name(node.type_name)
        if isinstance(node, ast.MultiVariableDeclaration):
            return typ + " " + ", ".join(item.name for item in node.var_names)
        name = (
            node.lhs.name
            if isinstance(node, ast.VariableDeclarationWithInitialization)
            else node.id.name
        )
        if node.ary_size is not None:
            typ = f"std::array<{typ}, {self.width(node.ary_size)}>"
        if isinstance(node, ast.VariableDeclarationWithInitialization):
            rhs = self.expression(node.rhs)
            if node.ary_size is not None:
                return f"{typ} {name} = {self._array_cast(dtype, node.rhs.type(self.symtab), rhs)}"
            if dtype.is_runtime and dtype.kind is TypeKind.BITS:
                return f"{typ} {name}({rhs}, {self.runtime_width(dtype, raw=True)})"
            return f"{typ} {name}({rhs})"
        if dtype.is_runtime:
            initializer = (
                "__UDB_HART"
                if dtype.kind is TypeKind.STRUCT
                else f"WidthArg({self.runtime_width(dtype)})"
            )
            return f"{typ} {name}{{{initializer}}}"
        return f"{typ} {name}"

    def _range_assignment(self, node):
        emit = self.expression
        rf = (
            self._register(node.variable.var)
            if isinstance(node.variable, ast.AryElementAccess)
            else None
        )
        destination = "__udb_reg_tmp" if rf else emit(node.variable)
        try:
            value = f"bit_insert<{self.known(node.msb)}, {self.known(node.lsb)}, {node.variable.type(self.symtab).width}>({destination}, {emit(node.write_value)})"
            text = f"{destination} = {value}"
        except IdlValueUnknown:
            text = f"bit_insert({destination}, {emit(node.msb)}, {emit(node.lsb)}, {emit(node.write_value)})"
        if rf:
            return f"__UDB_HART->_set_{rf}reg({emit(node.variable.index)}, ([&]() {{ auto __udb_reg_tmp = {emit(node.variable)}; {text}; return __udb_reg_tmp; }}()))"
        return text

    def statement(self, node: ast.Node, indent: int = 0) -> str:
        emit = self.expression
        pad = " " * indent
        if isinstance(node, (ast.FunctionBody, ast.IfBody)):
            return "\n".join(self.statement(child, indent) for child in node.stmts)
        if isinstance(node, ast.Comment):
            return ""
        if isinstance(node, ast.Statement):
            return pad + emit(node.action) + ";"
        if isinstance(node, (ast.ReturnStatement, ast.ReturnExpression)):
            values = node.return_value_nodes
            if not values:
                return pad + "return;"
            expected = node.expected_return_type(self.symtab)
            types = expected.tuple_types if len(values) > 1 else (expected,)
            arguments = []
            for value, dtype in zip(values, types, strict=True):
                if isinstance(value, ast.DontCareReturn):
                    initializer = (
                        "__UDB_HART" if dtype.is_runtime and dtype.kind is TypeKind.STRUCT else ""
                    )
                    arguments.append(f"{cpp_type(dtype)}{{{initializer}}}")
                else:
                    arguments.append(emit(value))
            value = (
                arguments[0]
                if len(values) == 1
                else "std::make_tuple(" + ", ".join(arguments) + ")"
            )
            return pad + "return " + value + ";"
        if isinstance(node, (ast.ConditionalReturnStatement, ast.ConditionalStatement)):
            action = (
                node.return_expression
                if isinstance(node, ast.ConditionalReturnStatement)
                else node.action
            )
            return f"{pad}if ({emit(node.condition)}) {{\n{self.statement(action, indent + 2)}\n{pad}}}"
        if isinstance(node, ast.If):
            parts = [f"{pad}if ({emit(node.if_cond)}) {{", self._block(node.if_body, indent + 2)]
            for branch in node.elseifs:
                parts += [
                    f"{pad}}} else if ({emit(branch.condition)}) {{",
                    self._block(branch.body, indent + 2),
                ]
            if node.final_else_body.stmts:
                parts += [f"{pad}}} else {{", self._block(node.final_else_body, indent + 2)]
            return "\n".join(parts + [pad + "}"])
        if isinstance(node, ast.ForLoop):
            self.symtab.push(node)
            try:
                init = emit(node.init)
                self.symtab.get(node.init.lhs.name).value = None
                condition, update = emit(node.condition), emit(node.update)
                body = "\n".join(self.statement(child, indent + 2) for child in node.stmts)
                return f"{pad}for ({init}; {condition}; {update}) {{\n{body}\n{pad}}}"
            finally:
                self.symtab.pop()
        return pad + emit(node) + ";"

    def _block(self, node, indent):
        self.symtab.push(node)
        try:
            return self.statement(node, indent)
        finally:
            self.symtab.pop()
