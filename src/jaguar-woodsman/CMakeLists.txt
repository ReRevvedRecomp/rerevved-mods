cmake_minimum_required(VERSION 3.25)
project(jaguar_woodsman LANGUAGES CXX)

include("${CMAKE_CURRENT_LIST_DIR}/../common/mod_cmake/rexmod.cmake")

rexmod_add_plugin(jaguar_woodsman mod_main.cpp)
if(UNIX)
    target_link_libraries(jaguar_woodsman PRIVATE ${CMAKE_DL_LIBS})
endif()
