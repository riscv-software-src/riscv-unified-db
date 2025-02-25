/*
 * SPDX-FileCopyrightText: Antmicro <www.antmicro.com>
 *
 * SPDX-License-Identifier: MIT
 */

#ifndef RENODE_IMPORTS_H_
#define RENODE_IMPORTS_H_

#ifdef __cplusplus
#define EXTERN_C extern "C"
#else
#define EXTERN_C
#endif

/* If this header is used as a part of tlib, we will call this hook after every callback */
#ifdef TARGET_LONG_BITS
EXTERN_C void tlib_try_interrupt_translation_block(void);
#else
#define tlib_try_interrupt_translation_block()
#endif

#include "udb/renode_map.h"

#define VA_NARGS_IMPL(_0, _1, _2, _3, _4, _5, _6, _7, _8, _9, _10, N, ...) N
#define VA_NARGS(ARGS...) VA_NARGS_IMPL(_, ##ARGS, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0)

#define CONCAT_0()
#define CONCAT_1(A) A
#define CONCAT_2(A, B) A##B
#define CONCAT_3(A, B, C) A##B##C
#define CONCAT_4(A, B, C, D) A##B##C##D
#define CONCAT_5(A, B, C, D, E) A##B##C##D##E
#define CONCAT_6(A, B, C, D, E, F) A##B##C##D##E##F
#define CONCAT_EXP_2(A, B) CONCAT_2(A, B)
#define CONCAT_EXP_5(A, B, C, D, E) CONCAT_5(A, B, C, D, E)

#define CONCAT_IMPL2(N, XS...) CONCAT_##N(XS)
#define CONCAT_IMPL(N, XS...) CONCAT_IMPL2(N, XS)
#define CONCAT(XS...) CONCAT_IMPL(VA_NARGS(XS), XS)

#define IF_THEN_ELSE(COND, THEN, ELSE) CONCAT_2(IF_THEN_ELSE_, COND)(THEN, ELSE)
#define IF_THEN_ELSE_0(THEN, ELSE) ELSE
#define IF_THEN_ELSE_1(THEN, ELSE) THEN

// We need these typedefs in order for the type name mapping based on token pasting to work
typedef void *voidptr;
typedef char *charptr;

#define CSHARP_TYPE_uint8_t Byte
#define CSHARP_TYPE_uint16_t UInt16
#define CSHARP_TYPE_uint32_t UInt32
#define CSHARP_TYPE_uint64_t UInt64
#define CSHARP_TYPE_int8_t SByte
#define CSHARP_TYPE_int16_t Int16
#define CSHARP_TYPE_int32_t Int32
#define CSHARP_TYPE_int64_t Int64
#define CSHARP_TYPE_charptr String
#define CSHARP_TYPE_voidptr IntPtr /* a pointer is a pointer */
#define CSHARP_TYPE_void           /* for return types */
#define CSHARP_TYPE_               /* for zero-arg functions */
#define CSHARP_TYPE(TYPE) CSHARP_TYPE_##TYPE

#define CSHARP_PREFIX_uint8_t Func
#define CSHARP_PREFIX_uint16_t Func
#define CSHARP_PREFIX_uint32_t Func
#define CSHARP_PREFIX_uint64_t Func
#define CSHARP_PREFIX_int8_t Func
#define CSHARP_PREFIX_int16_t Func
#define CSHARP_PREFIX_int32_t Func
#define CSHARP_PREFIX_int64_t Func
#define CSHARP_PREFIX_charptr Func
#define CSHARP_PREFIX_voidptr Func
#define CSHARP_PREFIX_void Action
#define CSHARP_PREFIX(TYPE) CSHARP_PREFIX_##TYPE

#define PARAMS_0() void
#define PARAMS_1(T0) T0 a0
#define PARAMS_2(T0, T1) PARAMS_1(T0), T1 a1
#define PARAMS_3(T0, T1, T2) PARAMS_2(T0, T1), T2 a2
#define PARAMS_4(T0, T1, T2, T3) PARAMS_3(T0, T1, T2), T3 a3
#define PARAMS_5(T0, T1, T2, T3, T4) PARAMS_4(T0, T1, T2, T3), T4 a4
#define PARAMS_6(T0, T1, T2, T3, T4, T5) PARAMS_5(T0, T1, T2, T3, T4), T5 a5
#define PARAMS_IMPL(N, TYPES...) CONCAT_EXP_2(PARAMS_, N)(TYPES)
#define PARAMS(TYPES...) PARAMS_IMPL(VA_NARGS(TYPES), TYPES)

#define PARAM_NAMES_0()
#define PARAM_NAMES_1(T0) a0
#define PARAM_NAMES_2(T0, T1) PARAM_NAMES_1(T0), a1
#define PARAM_NAMES_3(T0, T1, T2) PARAM_NAMES_2(T0, T1), a2
#define PARAM_NAMES_4(T0, T1, T2, T3) PARAM_NAMES_3(T0, T1, T2), a3
#define PARAM_NAMES_5(T0, T1, T2, T3, T4) PARAM_NAMES_4(T0, T1, T2, T3), a4
#define PARAM_NAMES_6(T0, T1, T2, T3, T4, T5) PARAM_NAMES_5(T0, T1, T2, T3, T4), a5
#define PARAM_NAMES_IMPL(N, TYPES...) CONCAT_EXP_2(PARAM_NAMES_, N)(TYPES)
#define PARAM_NAMES(TYPES...) PARAM_NAMES_IMPL(VA_NARGS(TYPES), TYPES)

#define RETURN_KEYWORD_Action
#define RETURN_KEYWORD_Func return
#define HAS_RETURN_Action 0
#define HAS_RETURN_Func 1
#define RETURN_KEYWORD(TYPE) CONCAT_EXP_2(RETURN_KEYWORD_, CSHARP_PREFIX(TYPE))
#define HAS_RETURN(TYPE) CONCAT_EXP_2(HAS_RETURN_, CSHARP_PREFIX(TYPE))

// Usage example: EXTERNAL_AS(int32_t, CSharpName, c_name, uint32_t, voidptr)
//
// Warning: for historical reasons, the return type goes FIRST in the generated
// renode_external_attach function name, which is reversed from the C# approach
// seen in delegate type parameters (as in Func<Arg1, Arg2, Ret>)
#define EXTERNAL_AS(RETURN_TYPE, IMPORTED_NAME, LOCAL_NAME, PARAMETER_TYPES...)                   \
    static RETURN_TYPE (*LOCAL_NAME##_callback$)(PARAMS(PARAMETER_TYPES));                        \
                                                                                                  \
    RETURN_TYPE LOCAL_NAME(PARAMS(PARAMETER_TYPES))                                               \
    {                                                                                             \
        /* If this function returns a value, generate code of the form                            \
         * uint32_t retval = (*callback)(); return retval;, possibly with something in between.   \
         * Otherwise, just call it. */                                                            \
        IF_THEN_ELSE(HAS_RETURN(RETURN_TYPE), RETURN_TYPE retval =,)                              \
        LOCAL_NAME##_callback$(PARAM_NAMES(PARAMETER_TYPES));                                     \
        tlib_try_interrupt_translation_block();                                                   \
        IF_THEN_ELSE(HAS_RETURN(RETURN_TYPE), return retval;,)                                    \
    }                                                                                             \
                                                                                                  \
    EXTERN_C UDB_EXPORT void CONCAT_EXP_5(renode_external_attach__, CSHARP_PREFIX(RETURN_TYPE),              \
                                CSHARP_TYPE(RETURN_TYPE),                                         \
                                CONCAT(MAP_LIST(CSHARP_TYPE, PARAMETER_TYPES)),                   \
                                __##IMPORTED_NAME(RETURN_TYPE (*param)(PARAMS(PARAMETER_TYPES)))) \
    {                                                                                             \
        LOCAL_NAME##_callback$ = param;                                                           \
    }

#define EXTERNAL(RETURN_TYPE, NAME, PARAMETER_TYPES...) \
    EXTERNAL_AS(RETURN_TYPE, $##NAME, NAME, PARAMETER_TYPES)

#endif
