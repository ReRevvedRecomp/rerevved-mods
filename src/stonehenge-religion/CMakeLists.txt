cmake_minimum_required(VERSION 3.25)
project(stonehenge_religion LANGUAGES CXX)

include("${CMAKE_CURRENT_LIST_DIR}/../common/mod_cmake/rexmod.cmake")

rexmod_add_plugin(stonehenge_religion mod_main.cpp)

if(UNIX)
    target_link_libraries(stonehenge_religion PRIVATE ${CMAKE_DL_LIBS})
endif()
