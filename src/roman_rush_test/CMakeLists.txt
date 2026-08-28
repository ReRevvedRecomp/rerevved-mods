cmake_minimum_required(VERSION 3.25)
project(roman_rush_test LANGUAGES CXX)

include("${CMAKE_CURRENT_LIST_DIR}/../common/mod_cmake/rexmod.cmake")

rexmod_add_plugin(roman_rush_test mod_main.cpp)
if(UNIX)
    target_link_libraries(roman_rush_test PRIVATE ${CMAKE_DL_LIBS})
endif()
