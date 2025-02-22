/**
 * @file   unit_soma_dataframe.cc
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
 * This file manages unit tests for the SOMADataFrame class
 */

#include <catch2/catch_template_test_macros.hpp>
#include <catch2/catch_test_macros.hpp>
#include <catch2/generators/catch_generators_all.hpp>
#include <catch2/matchers/catch_matchers_exception.hpp>
#include <catch2/matchers/catch_matchers_floating_point.hpp>
#include <catch2/matchers/catch_matchers_predicate.hpp>
#include <catch2/matchers/catch_matchers_string.hpp>
#include <catch2/matchers/catch_matchers_templated.hpp>
#include <catch2/matchers/catch_matchers_vector.hpp>
#include <numeric>
#include <random>

#include <tiledb/tiledb>
#include <tiledbsoma/tiledbsoma>
#include "utils/util.h"

using namespace tiledb;
using namespace tiledbsoma;
using namespace Catch::Matchers;

#ifndef TILEDBSOMA_SOURCE_ROOT
#define TILEDBSOMA_SOURCE_ROOT "not_defined"
#endif

const std::string src_path = TILEDBSOMA_SOURCE_ROOT;

namespace {
ArraySchema create_schema(Context& ctx, bool allow_duplicates = false) {
    // Create schema
    ArraySchema schema(ctx, TILEDB_DENSE);

    auto dim = Dimension::create<int64_t>(ctx, "d0", {0, 1000});

    Domain domain(ctx);
    domain.add_dimension(dim);
    schema.set_domain(domain);

    auto attr = Attribute::create<int>(ctx, "a0");
    schema.add_attribute(attr);
    schema.set_allows_dups(allow_duplicates);
    schema.check();

    return schema;
}
};  // namespace

TEST_CASE("SOMADataFrame: basic") {
    auto ctx = std::make_shared<Context>();
    std::string uri = "mem://unit-test-dataframe-basic";

    SOMADataFrame::create(ctx, uri, create_schema(*ctx));

    auto soma_dataframe = SOMADataFrame::open(TILEDB_READ, ctx, uri);
    REQUIRE(soma_dataframe->uri() == uri);
    REQUIRE(soma_dataframe->ctx() == ctx);
    auto schema = soma_dataframe->schema();
    REQUIRE(schema->has_attribute("a0"));
    REQUIRE(schema->domain().has_dimension("d0"));
    std::vector<std::string> expected_index_column_names = {"d0"};
    REQUIRE(
        soma_dataframe->index_column_names() == expected_index_column_names);
    REQUIRE(soma_dataframe->count() == 1);
    soma_dataframe->close();

    std::vector<int64_t> d0{1, 10};
    std::vector<int> a0(10, 1);

    auto array_buffer = std::make_shared<ArrayBuffers>();
    array_buffer->emplace("a0", ColumnBuffer::create(*schema, "a0", a0));
    array_buffer->emplace("d0", ColumnBuffer::create(*schema, "d0", d0));

    soma_dataframe->open(TILEDB_WRITE);
    soma_dataframe->write(array_buffer);
    soma_dataframe->close();

    soma_dataframe->open(TILEDB_READ);
    while (auto batch = soma_dataframe->read_next()) {
        auto arrbuf = batch.value();
        auto d0span = arrbuf->at("d0")->data<int64_t>();
        auto a0span = arrbuf->at("a0")->data<int>();
        REQUIRE(
            std::vector<int64_t>{1, 2, 3, 4, 5, 6, 7, 8, 9, 10} ==
            std::vector<int64_t>(d0span.begin(), d0span.end()));
        REQUIRE(a0 == std::vector<int>(a0span.begin(), a0span.end()));
    }
    soma_dataframe->close();
}