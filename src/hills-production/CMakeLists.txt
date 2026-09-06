cmake_minimum_required(VERSION 3.25)
project(hills_production LANGUAGES CXX)

include("${CMAKE_CURRENT_LIST_DIR}/../common/mod_cmake/rexmod.cmake")

rexmod_add_plugin(hills_production mod_main.cpp)

if(UNIX)
    target_link_libraries(hills_production PRIVATE ${CMAKE_DL_LIBS})
endif()
