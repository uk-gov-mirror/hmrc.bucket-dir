import httpretty
import pytest
import re
import sys

import bucket_dir

from unittest import mock


def index_created_correctly(items, page_name, root_index=False):
    regular_expressions = [
        f"<title>Index of {page_name}</title>",
        f"<h1>Index of {page_name}</h1>",
        '<address style="font-size:small;">Generated by <a href="https://github.com/hmrc/bucket-dir">bucket-dir</a>.</address>',
    ]
    if not root_index:
        regular_expressions.append('<a href="\.\.\/" class="parent_link">\.\.\/<\/a><\/br>')
    for item in items:
        regular_expressions.append(
            f"<a href=\"{item['name']}\" class=\"item_link\">{item['name']}<\/a>\s+{item['last_modified']}\s+{item['size']}\\n"
        )
    for captured_request in httpretty.latest_requests():
        body = captured_request.body.decode()
        regular_expressions_checklist = {
            regular_expression: False for regular_expression in regular_expressions
        }
        for regular_expression in regular_expressions:
            if re.search(regular_expression, body):
                regular_expressions_checklist[regular_expression] = True
        if all(regular_expressions_checklist.values()):
            if len(items) == body.count('class="item_link"'):
                return True
    return False


def simulate_s3(folders):
    httpretty.enable(allow_net_connect=False)
    httpretty.register_uri(
        httpretty.GET,
        "https://foo-bucket.s3.amazonaws.com/?list-type=2&max-keys=1000&encoding-type=url",
        body=f"""<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
    <Name>foo-bucket</Name>
    <Prefix></Prefix>
    <KeyCount>9</KeyCount>
    <MaxKeys>1000</MaxKeys>
    <EncodingType>url</EncodingType>
    <IsTruncated>false</IsTruncated>
    <Contents>
        <Key>root-one</Key>
        <LastModified>2021-02-22T10:23:44.000Z</LastModified>
        <ETag>&quot;18f190bd12aa40e3e7199c665e8fcc9c&quot;</ETag>
        <Size>30087</Size>
        <StorageClass>STANDARD</StorageClass>
    </Contents>
    <Contents>
        <Key>root-two</Key>
        <LastModified>2021-02-22T10:24:21.000Z</LastModified>
        <ETag>&quot;5b111fddb5257c3a2ddcb1d34deb455b&quot;</ETag>
        <Size>10801</Size>
        <StorageClass>STANDARD</StorageClass>
    </Contents>
    <Contents>
        <Key>regular-folder/object-one.foo</Key>
        <LastModified>2021-02-22T10:22:36.000Z</LastModified>
        <ETag>&quot;ccdab8fb019e23387203c06c157d302f-2&quot;</ETag>
        <Size>16524288</Size>
        <StorageClass>STANDARD</StorageClass>
    </Contents>
    <Contents>
        <Key>regular-folder/object-two.bar</Key>
        <LastModified>2021-02-22T10:23:11.000Z</LastModified>
        <ETag>&quot;13fa4f75b40ae3fbcb1bc1afb870fc0c&quot;</ETag>
        <Size>26921</Size>
        <StorageClass>STANDARD</StorageClass>
    </Contents>
    <Contents>
        <Key>regular-folder/index.html</Key>
        <LastModified>2021-02-22T10:28:13.000Z</LastModified>
        <ETag>&quot;13fa4f75b40ae3fbcb1bc1afb870fc0c&quot;</ETag>
        <Size>26921</Size>
        <StorageClass>STANDARD</StorageClass>
    </Contents>
        <Contents>
        <Key>deep-folder/i/ii/iii/deep-object</Key>
        <LastModified>2021-02-22T10:26:36.000Z</LastModified>
        <ETag>&quot;ccdab8fb019e23387203c06c157d302f-2&quot;</ETag>
        <Size>16524288</Size>
        <StorageClass>STANDARD</StorageClass>
    </Contents>
</ListBucketResult>""",
    )
    for folder in folders:
        httpretty.register_uri(
            httpretty.PUT,
            f"https://foo-bucket.s3.amazonaws.com{folder}index.html",
            body=put_object_request_callback,
        )


def put_object_request_callback(request, uri, response_headers):
    status = 100
    if len(request.body) > 0:
        status = 200
    return [status, {}, "".encode()]


@mock.patch.object(sys, "argv", ["bucket-dir", "foo-bucket"])
def test_generate_bucket_dir(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "foo-aws-access-key-id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "foo-aws-secret-access-key")
    simulate_s3(
        folders=[
            "/",
            "/deep-folder/",
            "/deep-folder/i/",
            "/deep-folder/i/ii/",
            "/deep-folder/i/ii/iii/",
            "/regular-folder/",
        ]
    )
    bucket_dir.run_cli()
    assert index_created_correctly(
        items=[
            {"name": "deep-folder/", "last_modified": "-", "size": "-"},
            {"name": "regular-folder/", "last_modified": "-", "size": "-"},
            {"name": "root-one", "last_modified": "22-Feb-2021 10:23", "size": "30.1 kB"},
            {"name": "root-two", "last_modified": "22-Feb-2021 10:24", "size": "10.8 kB"},
        ],
        page_name="foo-bucket/",
        root_index=True,
    )
    assert index_created_correctly(
        items=[
            {"name": "object-one.foo", "last_modified": "22-Feb-2021 10:22", "size": "16.5 MB"},
            {"name": "object-two.bar", "last_modified": "22-Feb-2021 10:23", "size": "26.9 kB"},
        ],
        page_name="foo-bucket/regular-folder/",
    )
    assert index_created_correctly(
        items=[{"name": "i/", "last_modified": "-", "size": "-"}],
        page_name="foo-bucket/deep-folder/",
    )
    assert index_created_correctly(
        items=[{"name": "ii/", "last_modified": "-", "size": "-"}],
        page_name="foo-bucket/deep-folder/i/",
    )
    assert index_created_correctly(
        items=[{"name": "iii/", "last_modified": "-", "size": "-"}],
        page_name="foo-bucket/deep-folder/i/ii/",
    )
    assert index_created_correctly(
        items=[{"name": "deep-object", "last_modified": "22-Feb-2021 10:26", "size": "16.5 MB"}],
        page_name="foo-bucket/deep-folder/i/ii/iii/",
    )


# TODO: Test against common structures
# <Contents>
#     <Key>empty-folder/</Key>
#     <LastModified>2021-02-22T10:23:25.000Z</LastModified>
#     <ETag>&quot;d41d8cd98f00b204e9800998ecf8427e&quot;</ETag>
#     <Size>0</Size>
#     <StorageClass>STANDARD</StorageClass>
# </Contents>
# <Contents>
#     <Key>folder+with+spaces/an+object+with+spaces</Key>
#     <LastModified>2021-02-22T10:24:37.000Z</LastModified>
#     <ETag>&quot;11490e1fc1376b0c209d05cf1190843f-4&quot;</ETag>
#     <Size>32993280</Size>
#     <StorageClass>STANDARD</StorageClass>
# </Contents>

# TODO: Test very advanced folder name
# See: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-keys.html#object-key-guidelines
# <Contents>
#     <Key>FOLDER_With_UnUsUaL_n4m3//it%5C%27gets*even.%28weirder%29///see%21</Key>
#     <LastModified>2021-02-22T10:26:16.000Z</LastModified>
#     <ETag>&quot;3e4b4b8018db93caccae34dc2fecc8d0&quot;</ETag>
#     <Size>22749</Size>
#     <StorageClass>STANDARD</StorageClass>
# </Contents>
