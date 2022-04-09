project(EdtReader)
cmake_minimum_required(VERSION 3.9)

add_executable(
  EdtReadExample
  EdtReader.cpp
  EdtReadExample.cpp)


add_executable(
  GridExample 
  GridExample.cpp)

add_executable(
  DisplayTinyEdt
  EdtReader.cpp
  DisplayTinyEdt.cpp)

