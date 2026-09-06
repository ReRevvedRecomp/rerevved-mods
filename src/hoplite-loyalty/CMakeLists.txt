cmake_minimum_required(VERSION 3.25)
project(hoplite_loyalty LANGUAGES CXX)

include("${CMAKE_CURRENT_LIST_DIR}/../common/mod_cmake/rexmod.cmake")

rexmod_add_plugin(hoplite_loyalty mod_main.cpp)
if(UNIX)
    target_link_libraries(hoplite_loyalty PRIVATE ${CMAKE_DL_LIBS})
endif()
