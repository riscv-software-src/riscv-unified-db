cmake_minimum_required(VERSION 3.20)
cmake_policy(SET CMP0067 NEW) # Force check_cxx_source_compiles to respect CMAKE_CXX_STANDARD

project(udb LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED True)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_CXX_FLAGS ${CMAKE_CXX_FLAGS} -no-pie)

include(CheckCXXSourceCompiles)

check_cxx_source_compiles(
  "
  #include <version>
  #if !defined(__cpp_concepts) || (__cpp_concepts < 201907)
  #error \"No concepts\"
  #endif
  int main(void) { return 0; }
  "
  HAVE_CONCEPTS
)
if (NOT HAVE_CONCEPTS)
  message(FATAL_ERROR "Compiler (${CMAKE_CXX_COMPILER}) does not support concepts")
endif()

include(FetchContent)

FetchContent_Declare(fmt
  GIT_REPOSITORY https://github.com/fmtlib/fmt.git
  GIT_TAG 10.2.1
)
FetchContent_MakeAvailable(fmt)

FetchContent_Declare(
  yaml-cpp
  GIT_REPOSITORY https://github.com/jbeder/yaml-cpp.git
  GIT_TAG yaml-cpp-0.7.0
)
FetchContent_MakeAvailable(yaml-cpp)

FetchContent_Declare(
    cli11_proj
    QUIET
    GIT_REPOSITORY https://github.com/CLIUtils/CLI11.git
    GIT_TAG f4d0731
)

FetchContent_MakeAvailable(cli11_proj)

FetchContent_Declare(
  Catch2
  GIT_REPOSITORY https://github.com/catchorg/Catch2.git
  GIT_TAG        v3.7.1
)

FetchContent_MakeAvailable(Catch2)

FetchContent_Declare(
  nlohmann_json_schema_validator
  GIT_REPOSITORY https://github.com/pboettch/json-schema-validator.git
  GIT_TAG        2.3.0
)

FetchContent_MakeAvailable(nlohmann_json_schema_validator)

#TODO remove when this works
set(CONFIG_LIST _)


set(GENERATED_SRCS "")
foreach(config ${CONFIG_LIST})
  list(APPEND GENERATED_SRCS "${CMAKE_SOURCE_DIR}/src/cfgs/${config}/decode.cxx")
  list(APPEND GENERATED_SRCS "${CMAKE_SOURCE_DIR}/src/cfgs/${config}/csrs.cxx")
  # list(APPEND GENERATED_SRCS "${CMAKE_SOURCE_DIR}/src/cfgs/${config}/params.cxx")
  # list(APPEND GENERATED_SRCS "${CMAKE_SOURCE_DIR}/src/cfgs/${config}/hart.cxx")
endforeach()

add_library(hart
  ${CMAKE_SOURCE_DIR}/src/db_data.cxx
  ${CMAKE_SOURCE_DIR}/src/version.cpp
  ${GENERATED_SRCS}
#  ../gen/iss/oryon/src/types.cxx
#  ../gen/iss/oryon/src/csr_types.cxx
#  ../gen/iss/oryon/src/hart_funcs.cxx
#  ../gen/iss/oryon/src/decode.cxx
)
target_include_directories(hart PUBLIC ${CMAKE_SOURCE_DIR}/include)
target_link_libraries(hart PUBLIC yaml-cpp::yaml-cpp nlohmann_json_schema_validator fmt::fmt -lgmp -lgmpxx)

add_executable(iss
  ${CMAKE_SOURCE_DIR}/src/iss.cpp
)
target_link_libraries(iss PRIVATE hart CLI11::CLI11)


## TESTS

add_executable(test_bits
  ${CMAKE_SOURCE_DIR}/test/test_bits.cpp
)
target_include_directories(test_bits PUBLIC ${CMAKE_SOURCE_DIR}/include)
target_link_libraries(test_bits PRIVATE hart Catch2::Catch2WithMain)

add_executable(test_util
  ${CMAKE_SOURCE_DIR}/test/test_util.cpp
)
target_include_directories(test_util PUBLIC ${CMAKE_SOURCE_DIR}/include)
target_link_libraries(test_util PRIVATE hart Catch2::Catch2WithMain)

add_executable(test_csr
  ${CMAKE_SOURCE_DIR}/test/test_csr.cpp
)
target_include_directories(test_csr PUBLIC ${CMAKE_SOURCE_DIR}/include)
# target_link_libraries(test_csr PRIVATE hart Catch2::Catch2WithMain)

add_executable(test_version
  ${CMAKE_SOURCE_DIR}/test/test_version.cpp
)
target_include_directories(test_version PUBLIC ${CMAKE_SOURCE_DIR}/include)
target_link_libraries(test_version PRIVATE hart Catch2::Catch2WithMain)

include(CTest)
include(Catch)
catch_discover_tests(test_bits test_util)
