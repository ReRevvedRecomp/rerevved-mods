cmake_minimum_required(VERSION 3.25)
project(aztec_jaguar_movement LANGUAGES CXX)

include("${CMAKE_CURRENT_LIST_DIR}/../common/mod_cmake/rexmod.cmake")

rexmod_add_plugin(aztec_jaguar_movement mod_main.cpp)
if(UNIX)
    target_link_libraries(aztec_jaguar_movement PRIVATE ${CMAKE_DL_LIBS})
endif()
