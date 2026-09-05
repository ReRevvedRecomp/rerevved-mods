cmake_minimum_required(VERSION 3.25)
project(roman_cataphracts_defense LANGUAGES CXX)

include("${CMAKE_CURRENT_LIST_DIR}/../common/mod_cmake/rexmod.cmake")

rexmod_add_plugin(roman_cataphracts_defense mod_main.cpp)
if(UNIX)
    target_link_libraries(roman_cataphracts_defense PRIVATE ${CMAKE_DL_LIBS})
endif()
