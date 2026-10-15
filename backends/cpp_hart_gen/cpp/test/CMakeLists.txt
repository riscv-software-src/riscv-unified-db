# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

cmake_minimum_required(VERSION 3.20)
project(udb_native_bits_tests LANGUAGES CXX)

get_filename_component(UDB_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../.." ABSOLUTE)
include("${UDB_ROOT}/.toolchain/check_cxx.cmake")
include(FetchContent)
set(FETCHCONTENT_UPDATES_DISCONNECTED ON CACHE BOOL "Use cached dependency sources")
FetchContent_Declare(fmt
  GIT_REPOSITORY https://github.com/fmtlib/fmt.git
  GIT_TAG 12.2.0
)
FetchContent_Declare(Catch2
  GIT_REPOSITORY https://github.com/catchorg/Catch2.git
  GIT_TAG v3.16.0
)
FetchContent_MakeAvailable(fmt Catch2)
enable_testing()
include("${CMAKE_CURRENT_LIST_DIR}/bits-tests.cmake")
