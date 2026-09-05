cmake_minimum_required(VERSION 3.25)
project(state_inspector LANGUAGES CXX)

include("${CMAKE_CURRENT_LIST_DIR}/../common/mod_cmake/rexmod.cmake")

rexmod_add_plugin(state_inspector mod_main.cpp)
if(UNIX)
    target_link_libraries(state_inspector PRIVATE ${CMAKE_DL_LIBS})
endif()
