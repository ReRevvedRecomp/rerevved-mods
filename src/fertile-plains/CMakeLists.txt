cmake_minimum_required(VERSION 3.25)
project(fertile_plains LANGUAGES CXX)

include("${CMAKE_CURRENT_LIST_DIR}/../common/mod_cmake/rexmod.cmake")

rexmod_add_plugin(fertile_plains mod_main.cpp)

if(UNIX)
    target_link_libraries(fertile_plains PRIVATE ${CMAKE_DL_LIBS})
endif()
