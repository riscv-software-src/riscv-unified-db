# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

get_filename_component(BITS_CPP_DIR "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
include(CheckCXXSourceCompiles)
include(CMakePushCheckState)
cmake_push_check_state(RESET)
set(CMAKE_REQUIRED_LIBRARIES gmpxx gmp)
# Probe through the selected compiler, which may run in the toolchain container.
check_cxx_source_compiles(
  "#include <gmpxx.h>\nint main() { mpz_class n = 123; return n.get_si() != 123; }"
  UDB_BITS_HAVE_GMP
)
cmake_pop_check_state()
if(NOT UDB_BITS_HAVE_GMP)
  message(FATAL_ERROR "The selected C++ toolchain requires GMP C++ headers and libraries")
endif()

add_executable(test_bits_properties
  "${CMAKE_CURRENT_LIST_DIR}/test_bits_properties_small.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/test_bits_properties_wide.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/test_bits_properties_signed.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/test_bits_properties_boundaries.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/test_bits_properties_runtime.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/test_bits_properties_runtime_signed.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/test_bits_properties_contracts.cpp"
)
target_include_directories(test_bits_properties PRIVATE
  "${BITS_CPP_DIR}/include"
)
target_link_libraries(test_bits_properties PRIVATE
  fmt::fmt Catch2::Catch2WithMain gmpxx gmp
)
target_compile_features(test_bits_properties PRIVATE cxx_std_23)
if(PROJECT_NAME STREQUAL "udb")
  target_compile_options(test_bits_properties PRIVATE -fprofile-arcs -ftest-coverage)
  target_link_options(test_bits_properties PRIVATE -fprofile-arcs -ftest-coverage)
endif()
option(UDB_BITS_UBSAN "Instrument the native Bits property target for undefined behavior" OFF)
if(UDB_BITS_UBSAN)
  target_compile_options(test_bits_properties PRIVATE -fsanitize=undefined -fno-sanitize-recover=undefined)
  target_link_options(test_bits_properties PRIVATE -fsanitize=undefined)
endif()

# Keep the legacy aggregate build target without generating test source.
add_custom_target(test_bits_random DEPENDS test_bits_properties)
list(APPEND CMAKE_MODULE_PATH "${Catch2_SOURCE_DIR}/extras")
include(Catch)
catch_discover_tests(test_bits_properties TEST_PREFIX "native_bits::" EXTRA_ARGS --rng-seed 1234)

add_executable(test_bits_runtime_defects
  "${CMAKE_CURRENT_LIST_DIR}/test_bits_compile_defects.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/test_bits_runtime_defects.cpp"
)
target_include_directories(test_bits_runtime_defects PRIVATE
  "${BITS_CPP_DIR}/include"
)
target_link_libraries(test_bits_runtime_defects PRIVATE
  fmt::fmt Catch2::Catch2WithMain gmpxx gmp
)
target_compile_features(test_bits_runtime_defects PRIVATE cxx_std_23)
catch_discover_tests(test_bits_runtime_defects TEST_PREFIX "defect_bits::" EXTRA_ARGS --rng-seed 1234)
add_dependencies(test_bits_random test_bits_runtime_defects)
if(UDB_BITS_UBSAN)
  target_compile_options(test_bits_runtime_defects PRIVATE -fsanitize=undefined -fno-sanitize-recover=undefined)
  target_link_options(test_bits_runtime_defects PRIVATE -fsanitize=undefined)
endif()

if(PROJECT_NAME STREQUAL "udb_native_bits_tests")
  add_executable(test_bits_directed "${CMAKE_CURRENT_LIST_DIR}/test_bits_directed.cpp")
  target_include_directories(test_bits_directed PRIVATE
    "${BITS_CPP_DIR}/include"
  )
  target_link_libraries(test_bits_directed PRIVATE
    fmt::fmt Catch2::Catch2WithMain gmpxx gmp
  )
  target_compile_features(test_bits_directed PRIVATE cxx_std_23)
  catch_discover_tests(test_bits_directed TEST_PREFIX "directed_bits::" EXTRA_ARGS --rng-seed 1234)
endif()
