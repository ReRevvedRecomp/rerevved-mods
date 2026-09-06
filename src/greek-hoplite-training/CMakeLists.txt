cmake_minimum_required(VERSION 3.25)
project(greek_hoplite_training LANGUAGES CXX)

include("${CMAKE_CURRENT_LIST_DIR}/../common/mod_cmake/rexmod.cmake")

rexmod_add_plugin(greek_hoplite_training mod_main.cpp)
if(UNIX)
    target_link_libraries(greek_hoplite_training PRIVATE ${CMAKE_DL_LIBS})
endif()
