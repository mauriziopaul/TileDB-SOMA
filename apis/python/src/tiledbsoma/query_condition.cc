/**
 * @file   query_condition.cc
 *
 * @section LICENSE
 *
 * The MIT License
 *
 * @copyright Copyright (c) 2022 TileDB, Inc.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 *
 * @section DESCRIPTION
 *
 *   This file implements the TileDB-Py query condition.
 */

// clang-format off
#include <pybind11/pybind11.h>
#include <pybind11/pytypes.h>

#include <exception>

// #define TILEDB_DEPRECATED
// #define TILEDB_DEPRECATED_EXPORT

// #include "util.h"
#include <tiledb/tiledb> // C++
#include <tiledbsoma/tiledbsoma>

#define TPY_ERROR_LOC(m) throw tiledbsoma::TileDBSOMAError(m);

#if TILEDB_VERSION_MAJOR == 2 && TILEDB_VERSION_MINOR >= 2

#if !defined(NDEBUG)
//#include "debug.cc"
#endif

namespace tiledbpy {

using namespace std;
using namespace tiledb;
namespace py = pybind11;
using namespace pybind11::literals;

class PyQueryCondition {

private:
  Context ctx_;
  shared_ptr<QueryCondition> qc_;

public:
  PyQueryCondition() = delete;

  PyQueryCondition(py::object ctx) {
    (void)ctx;
    try {
      // create one global context for all query conditions
      static Context context = Context();
      ctx_ = context;
      qc_ = shared_ptr<QueryCondition>(new QueryCondition(ctx_));
    } catch (TileDBError &e) {
      TPY_ERROR_LOC(e.what());
    }
  }

  void init(const string &attribute_name, const string &condition_value,
            tiledb_query_condition_op_t op) {
    try {
      qc_->init(attribute_name, condition_value, op);
    } catch (TileDBError &e) {
      TPY_ERROR_LOC(e.what());
    }
  }

  template <typename T>
  void init(const string &attribute_name, T condition_value,
            tiledb_query_condition_op_t op) {
    try {
      qc_->init(attribute_name, &condition_value, sizeof(condition_value), op);
    } catch (TileDBError &e) {
      TPY_ERROR_LOC(e.what());
    }
  }

  shared_ptr<QueryCondition> ptr() { return qc_; }

  py::capsule __capsule__() { return py::capsule(&qc_, "qc"); }

  PyQueryCondition
  combine(PyQueryCondition rhs,
          tiledb_query_condition_combination_op_t combination_op) const {

    auto pyqc = PyQueryCondition(nullptr, ctx_.ptr().get());

    tiledb_query_condition_t *combined_qc = nullptr;
    ctx_.handle_error(
        tiledb_query_condition_alloc(ctx_.ptr().get(), &combined_qc));

    ctx_.handle_error(tiledb_query_condition_combine(
        ctx_.ptr().get(), qc_->ptr().get(), rhs.qc_->ptr().get(),
        combination_op, &combined_qc));

    pyqc.qc_ = std::shared_ptr<QueryCondition>(
        new QueryCondition(pyqc.ctx_, combined_qc));

    return pyqc;
  }

private:
  PyQueryCondition(shared_ptr<QueryCondition> qc, tiledb_ctx_t *c_ctx)
      : qc_(qc) {
    ctx_ = Context(c_ctx, false);
  }

  void set_ctx(py::object ctx) {
    tiledb_ctx_t *c_ctx;
    if ((c_ctx = (py::capsule)ctx.attr("__capsule__")()) == nullptr)
      TPY_ERROR_LOC("Invalid context pointer!")
    
    ctx_ = Context(c_ctx, false);
  }
}; // namespace tiledbpy

void init_query_condition(py::module &m) {
  py::class_<PyQueryCondition>(m, "PyQueryCondition", py::module_local())
      .def(py::init<py::object>(), py::arg("ctx") = py::none())

      /* TODO surely there's a better way to deal with templated PyBind11
       * functions? but maybe not?
       * https://github.com/pybind/pybind11/issues/1667
       */

      .def("init_string",
           static_cast<void (PyQueryCondition::*)(
               const string &, const string &, tiledb_query_condition_op_t)>(
               &PyQueryCondition::init))

      .def("init_uint64",
           static_cast<void (PyQueryCondition::*)(const string &, uint64_t,
                                                  tiledb_query_condition_op_t)>(
               &PyQueryCondition::init))
      .def("init_int64",
           static_cast<void (PyQueryCondition::*)(const string &, int64_t,
                                                  tiledb_query_condition_op_t)>(
               &PyQueryCondition::init))
      .def("init_uint32",
           static_cast<void (PyQueryCondition::*)(const string &, uint32_t,
                                                  tiledb_query_condition_op_t)>(
               &PyQueryCondition::init))
      .def("init_int32",
           static_cast<void (PyQueryCondition::*)(const string &, int32_t,
                                                  tiledb_query_condition_op_t)>(
               &PyQueryCondition::init))
      .def("init_uint16",
           static_cast<void (PyQueryCondition::*)(const string &, uint16_t,
                                                  tiledb_query_condition_op_t)>(
               &PyQueryCondition::init))
      .def("init_int16",
           static_cast<void (PyQueryCondition::*)(const string &, int16_t,
                                                  tiledb_query_condition_op_t)>(
               &PyQueryCondition::init))
      .def("init_uint8",
           static_cast<void (PyQueryCondition::*)(const string &, uint8_t,
                                                  tiledb_query_condition_op_t)>(
               &PyQueryCondition::init))
      .def("init_int8",
           static_cast<void (PyQueryCondition::*)(const string &, int8_t,
                                                  tiledb_query_condition_op_t)>(
               &PyQueryCondition::init))

      .def("init_float32",
           static_cast<void (PyQueryCondition::*)(const string &, float,
                                                  tiledb_query_condition_op_t)>(
               &PyQueryCondition::init))
      .def("init_float64",
           static_cast<void (PyQueryCondition::*)(const string &, double,
                                                  tiledb_query_condition_op_t)>(
               &PyQueryCondition::init))
      .def("init_bool",
           static_cast<void (PyQueryCondition::*)(const string &, bool,
                                                  tiledb_query_condition_op_t)>(
               &PyQueryCondition::init))

      .def("combine", &PyQueryCondition::combine)

      .def("__capsule__", &PyQueryCondition::__capsule__);

  py::enum_<tiledb_query_condition_op_t>(m, "tiledb_query_condition_op_t",
                                         py::arithmetic(), py::module_local())
      .value("TILEDB_LT", TILEDB_LT)
      .value("TILEDB_LE", TILEDB_LE)
      .value("TILEDB_GT", TILEDB_GT)
      .value("TILEDB_GE", TILEDB_GE)
      .value("TILEDB_EQ", TILEDB_EQ)
      .value("TILEDB_NE", TILEDB_NE)
      .export_values();

  py::enum_<tiledb_query_condition_combination_op_t>(
      m, "tiledb_query_condition_combination_op_t", py::arithmetic(), py::module_local())
      .value("TILEDB_AND", TILEDB_AND)
      .value("TILEDB_OR", TILEDB_OR)
      .export_values();
}
}; // namespace tiledbpy

#endif
