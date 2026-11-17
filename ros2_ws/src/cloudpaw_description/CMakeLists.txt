cmake_minimum_required(VERSION 3.8)
project(cloudpaw_description)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})
install(DIRECTORY urdf launch config DESTINATION share/${PROJECT_NAME})
install(PROGRAMS scripts/trot_gait.py scripts/gz_trot.py DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_gait test/test_gait.py)
endif()

ament_package()
