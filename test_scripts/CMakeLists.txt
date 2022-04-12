project(TestScripts)
cmake_minimum_required(VERSION 3.9)

add_executable(
  EdtUtilsTest
  ../EdtReader/EdtReader.cpp
  test_edt_utils.cpp)
