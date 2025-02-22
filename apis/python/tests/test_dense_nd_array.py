import pathlib
from typing import Tuple

import numpy as np
import pyarrow as pa
import pytest
import tiledb

import tiledbsoma as soma
from tiledbsoma.options import SOMATileDBContext

from . import NDARRAY_ARROW_TYPES_NOT_SUPPORTED, NDARRAY_ARROW_TYPES_SUPPORTED


@pytest.mark.parametrize(
    "shape", [(10,), (1, 100), (10, 1, 100), (2, 4, 6, 8), [1], (1, 2, 3, 4, 5)]
)
@pytest.mark.parametrize("element_type", NDARRAY_ARROW_TYPES_SUPPORTED)
def test_dense_nd_array_create_ok(
    tmp_path, shape: Tuple[int, ...], element_type: pa.DataType
):
    """
    Test all cases we expect "create" to succeed.
    """
    assert pa.types.is_primitive(element_type)  # sanity check incoming params

    with pytest.raises(TypeError):
        soma.DenseNDArray.create(
            tmp_path.as_posix(), type=element_type.to_pandas_dtype(), shape=shape
        )
    a = soma.DenseNDArray.create(tmp_path.as_posix(), type=element_type, shape=shape)
    assert soma.DenseNDArray.exists(tmp_path.as_posix())
    assert not soma.SparseNDArray.exists(tmp_path.as_posix())
    assert not soma.Measurement.exists(tmp_path.as_posix())
    assert a.soma_type == "SOMADenseNDArray"
    assert a.uri == tmp_path.as_posix()
    assert a.ndim == len(shape)
    assert a.shape == tuple(shape)
    assert a.is_sparse is False

    assert a.schema is not None
    expected_field_names = ["soma_data"] + [f"soma_dim_{d}" for d in range(len(shape))]
    assert set(a.schema.names) == set(expected_field_names)
    for d in range(len(shape)):
        assert a.schema.field(f"soma_dim_{d}").type == pa.int64()
    assert a.schema.field("soma_data").type == element_type

    # Validate TileDB array schema
    with tiledb.open(tmp_path.as_posix()) as A:
        assert not A.schema.sparse


@pytest.mark.parametrize("shape", [(10,)])
@pytest.mark.parametrize("element_type", NDARRAY_ARROW_TYPES_NOT_SUPPORTED)
def test_dense_nd_array_create_fail(
    tmp_path, shape: Tuple[int, ...], element_type: pa.DataType
):
    with pytest.raises(TypeError):
        soma.DenseNDArray.create(tmp_path.as_posix(), type=element_type, shape=shape)


@pytest.mark.parametrize("shape", [(10,), (10, 20), (10, 20, 2), (2, 4, 6, 8)])
def test_dense_nd_array_read_write_tensor(tmp_path, shape: Tuple[int, ...]):
    a = soma.DenseNDArray.create(tmp_path.as_posix(), type=pa.float64(), shape=shape)
    ndim = len(shape)

    # random sample -- written to entire array
    data = np.random.default_rng().standard_normal(np.prod(shape)).reshape(shape)
    coords = tuple(slice(0, dim_len) for dim_len in shape)
    with pytest.raises(TypeError):
        a.write(coords, data)
    a.write(coords, pa.Tensor.from_numpy(data))
    del a

    # check multiple read paths
    with soma.DenseNDArray.open(tmp_path.as_posix()) as b:

        t = b.read((slice(None),) * ndim, result_order="row-major")
        assert t.equals(pa.Tensor.from_numpy(data))

        t = b.read((slice(None),) * ndim, result_order="column-major")
        assert t.equals(pa.Tensor.from_numpy(data.transpose()))

    # Validate TileDB array schema
    with tiledb.open(tmp_path.as_posix()) as A:
        assert not A.schema.sparse

    # write a single-value sub-array and recheck
    with soma.DenseNDArray.open(tmp_path.as_posix(), "w") as c:
        c.write(
            (0,) * len(shape),
            pa.Tensor.from_numpy(np.zeros((1,) * len(shape), dtype=np.float64)),
        )
        data[(0,) * len(shape)] = 0.0
    with soma.DenseNDArray.open(tmp_path.as_posix()) as c:
        t = c.read((slice(None),) * ndim)
    assert t.equals(pa.Tensor.from_numpy(data))


@pytest.mark.parametrize("shape", [(), (0,), (10, 0), (0, 10), (1, 2, 0)])
def test_zero_length_fail(tmp_path, shape):
    """Zero length dimensions are expected to fail"""
    with pytest.raises(ValueError):
        soma.DenseNDArray.create(tmp_path.as_posix(), type=pa.float32(), shape=shape)


def test_dense_nd_array_reshape(tmp_path):
    """
    Reshape currently unimplemented.
    """
    a = soma.DenseNDArray.create(
        tmp_path.as_posix(), type=pa.int32(), shape=(10, 10, 10)
    )
    with pytest.raises(NotImplementedError):
        assert a.reshape((100, 10, 1))


@pytest.mark.parametrize("shape_is_numeric", [True, False])
def test_dense_nd_array_requires_shape(tmp_path, shape_is_numeric):
    uri = tmp_path.as_posix()

    if shape_is_numeric:
        soma.DenseNDArray.create(
            uri,
            type=pa.float32(),
            shape=(2, 3),
        ).close()
        assert soma.DenseNDArray.exists(uri)
        with soma.DenseNDArray.open(uri) as dnda:
            assert dnda.shape == (2, 3)
    else:
        with pytest.raises(ValueError):
            soma.DenseNDArray.create(uri, type=pa.float32(), shape=(None, None)).close()


@pytest.mark.parametrize(
    "io",
    [
        {
            "name": "(2, 3)",
            "coords": (2, 3),
            "output": np.array([[203]]),
        },
        {
            "name": "([:], 3)",
            "coords": (slice(None), 3),
            "output": np.array([[3], [103], [203], [303]]),
        },
        {
            "name": "(2, [:])",
            "coords": (2, slice(None)),
            "output": np.array([[200, 201, 202, 203, 204, 205]]),
        },
        {
            "name": "(2,)",
            "coords": (2,),
            "output": np.array([[200, 201, 202, 203, 204, 205]]),
        },
        {
            "name": "([:2], [5:])",
            "coords": (slice(None, 2), slice(5, None)),
            "output": np.array([[5], [105], [205]]),
        },
        {
            "name": "([0:2], [5:5])",
            "coords": (slice(0, 2), slice(5, 5)),
            "output": np.array([[5], [105], [205]]),
        },
        {
            "name": "()",
            "coords": (),
            "output": np.array(
                [
                    [0, 1, 2, 3, 4, 5],
                    [100, 101, 102, 103, 104, 105],
                    [200, 201, 202, 203, 204, 205],
                    [300, 301, 302, 303, 304, 305],
                ]
            ),
        },
        {
            "name": "([:], [:]) multiple reads",
            "coords": (slice(None), slice(None)),
            "cfg": {
                "soma.init_buffer_bytes": 100
            },  # Known small enough to force multiple reads
            "output": np.array(
                [
                    [0, 1, 2, 3, 4, 5],
                    [100, 101, 102, 103, 104, 105],
                    [200, 201, 202, 203, 204, 205],
                    [300, 301, 302, 303, 304, 305],
                ]
            ),
        },
    ],
    ids=lambda io: io.get("name"),
)
def test_dense_nd_array_slicing(tmp_path, io):
    """
    We already have tests that check n-d for various values of n. This one (which happens to use 2-d
    data, though not in an essential way) checks subarray slicing. In particular, it validates
    SOMA's doubly-inclusive slice indexing semantics against Python's singly-inclusive slicing
    semantics, ensuring that none of the latter has crept into the former.
    """
    cfg = {}
    if "cfg" in io:
        cfg = io["cfg"]
    context = SOMATileDBContext(tiledb_ctx=tiledb.Ctx(cfg))

    nr = 4
    nc = 6

    with soma.DenseNDArray.create(
        tmp_path.as_posix(), type=pa.int64(), shape=(nr, nc), context=context
    ) as a:
        npa = np.zeros((nr, nc))
        for i in range(nr):
            for j in range(nc):
                npa[i, j] = 100 * i + j
        a.write(coords=(slice(0, nr), slice(0, nc)), values=pa.Tensor.from_numpy(npa))

    with soma.DenseNDArray.open(tmp_path.as_posix()) as a:
        if "throws" in io:
            with pytest.raises(io["throws"]):
                a.read(io["coords"]).to_numpy()
        else:
            output = a.read(io["coords"]).to_numpy()
            assert np.all(output == io["output"])


@pytest.mark.parametrize(
    "io",
    [
        {
            "name": "negative",
            "shape": (10,),
            "coords": (-1,),
            "throws": (RuntimeError, tiledb.cc.TileDBError),
        },
        {
            "name": "12 in 10 domain",
            "shape": (10,),
            "coords": (12,),
            "throws": (RuntimeError, tiledb.cc.TileDBError),
        },
        {
            "name": "too many dims",
            "shape": (10,),
            "coords": (
                2,
                3,
            ),
            "throws": ValueError,
        },
        {
            "name": "too many dims 2",
            "shape": (10, 20),
            "coords": (
                2,
                3,
                4,
            ),
            "throws": ValueError,
        },
        {
            "name": "oops all negatives",
            "shape": (10, 20),
            "coords": (slice(-2, -1),),
            "throws": ValueError,
        },
        {
            "name": "too big",
            "shape": (5,),
            "coords": (slice(10, 20),),
            "throws": ValueError,
        },
        {
            "name": "slice step",
            "shape": (10, 20),
            "coords": (slice(2, 3, -1),),
            "throws": ValueError,
        },
        {
            "name": "slice step 2",
            "shape": (10, 20),
            "coords": (slice(3, 2, 1),),
            "throws": ValueError,
        },
        {
            "name": "slice step 3",
            "shape": (10, 20),
            "coords": (slice(4, 8, 2),),
            "throws": ValueError,
        },
        {
            "name": "too many dims pa.array",
            "shape": (10, 20),
            "coords": (
                pa.array(
                    [1, 2, 3],
                )
            ),
            "throws": ValueError,
        },
    ],
    ids=lambda io: io.get("name"),
)
def test_dense_nd_array_indexing_errors(tmp_path, io):
    shape = io["shape"]
    read_coords = io["coords"]

    with soma.DenseNDArray.create(
        tmp_path.as_posix(), type=pa.int64(), shape=shape
    ) as a:

        npa = np.random.default_rng().standard_normal(np.prod(shape)).reshape(shape)

        write_coords = tuple(slice(0, dim_len) for dim_len in shape)
        a.write(coords=write_coords, values=pa.Tensor.from_numpy(npa))

    with soma.DenseNDArray.open(tmp_path.as_posix()) as a:
        with pytest.raises(io["throws"]):
            a.read(coords=read_coords).to_numpy()


def test_tile_extents(tmp_path):
    soma.DenseNDArray.create(
        tmp_path.as_posix(),
        type=pa.float32(),
        shape=(100, 10000),
        platform_config={
            "tiledb": {
                "create": {
                    "dims": {
                        "soma_dim_0": {"tile": 2048},
                        "soma_dim_1": {"tile": 2048},
                    }
                }
            }
        },
    ).close()

    with tiledb.open(tmp_path.as_posix()) as A:
        assert A.schema.domain.dim(0).tile == 100
        assert A.schema.domain.dim(1).tile == 2048


def test_timestamped_ops(tmp_path):
    # 2x2 array
    with soma.DenseNDArray.create(
        tmp_path.as_posix(),
        type=pa.uint8(),
        shape=(2, 2),
        context=SOMATileDBContext(timestamp=1),
    ) as a:
        a.write(
            (slice(0, 2), slice(0, 2)),
            pa.Tensor.from_numpy(np.zeros((2, 2), dtype=np.uint8)),
        )

    # write 1 into top-left entry @ t=10
    with soma.DenseNDArray.open(
        tmp_path.as_posix(), mode="w", context=SOMATileDBContext(timestamp=10)
    ) as a:
        a.write(
            (slice(0, 1), slice(0, 1)),
            pa.Tensor.from_numpy(np.ones((1, 1), dtype=np.uint8)),
        )

    # write 1 into bottom-right entry @ t=20
    with soma.DenseNDArray.open(
        uri=tmp_path.as_posix(), mode="w", context=SOMATileDBContext(timestamp=20)
    ) as a:
        a.write(
            (slice(1, 2), slice(1, 2)),
            pa.Tensor.from_numpy(np.ones((1, 1), dtype=np.uint8)),
        )

    # read with no timestamp args & see both 1s
    with soma.DenseNDArray.open(tmp_path.as_posix()) as a:
        assert a.read((slice(None), slice(None))).to_numpy().tolist() == [
            [1, 0],
            [0, 1],
        ]

    # read @ t=15 & see only the writes up til then
    with soma.DenseNDArray.open(
        tmp_path.as_posix(), context=SOMATileDBContext(timestamp=15)
    ) as a:
        assert a.read((slice(0, 1), slice(0, 1))).to_numpy().tolist() == [
            [1, 0],
            [0, 0],
        ]


def test_fixed_timestamp(tmp_path: pathlib.Path):
    fixed_time = SOMATileDBContext(timestamp=999)
    with soma.DenseNDArray.create(
        tmp_path.as_posix(),
        type=pa.uint8(),
        shape=(2, 2),
        context=fixed_time,
    ) as ndarr:
        assert ndarr.tiledb_timestamp_ms == 999
        ndarr.metadata["metadata"] = "created"

    with soma.open(tmp_path.as_posix(), context=fixed_time) as ndarr_read:
        assert ndarr_read.tiledb_timestamp_ms == 999
        assert ndarr_read.metadata["metadata"] == "created"

    with soma.open(
        tmp_path.as_posix(), context=fixed_time, tiledb_timestamp=1000
    ) as read_1000:
        assert read_1000.tiledb_timestamp_ms == 1000
        assert read_1000.metadata["metadata"] == "created"

    with pytest.raises(soma.SOMAError):
        soma.open(tmp_path.as_posix(), context=fixed_time, tiledb_timestamp=111)
