# frozen_string_literal: true

require_relative 'test_helper'
require "English"
require "minitest/autorun"
require "backend_helpers"

include TemplateHelpers

$root ||= (Pathname.new(__FILE__) / ".." / ".." / "..").realpath

class TestBackendHelpers < Minitest::Test
  def test_ext
    assert_equal("%%UDB_DOC_LINK%ext;foo;foo%%", link_to_udb_doc_ext("foo"))
    assert_equal("[#udb:doc:ext:foo]", anchor_for_udb_doc_ext("foo"))
    assert_equal("%%UDB_DOC_LINK%ext;fo_o;fo.o%%", link_to_udb_doc_ext("fo.o"))
    assert_equal("[#udb:doc:ext:fo_o]", anchor_for_udb_doc_ext("fo.o"))
  end

  def test_ext_param
    assert_equal("%%UDB_DOC_LINK%ext_param;foo.bar;zort%%", link_to_udb_doc_ext_param("foo","bar","zort"))
    assert_equal("[#udb:doc:ext_param:foo:bar]", anchor_for_udb_doc_ext_param("foo","bar"))
    assert_equal("%%UDB_DOC_LINK%ext_param;fo_o.bar;fluffy%%", link_to_udb_doc_ext_param("fo.o","bar","fluffy"))
    assert_equal("[#udb:doc:ext_param:fo_o:bar]", anchor_for_udb_doc_ext_param("fo.o","bar"))
    assert_raises(ArgumentError) { link_to_udb_doc_ext_param("foo","ba.r","fluffy") }
    assert_raises(ArgumentError) { anchor_for_udb_doc_ext_param("foo","ba.r") }
  end

  def test_inst
    assert_equal("%%UDB_DOC_LINK%inst;foo;foo%%", link_to_udb_doc_inst("foo"))
    assert_equal("[#udb:doc:inst:foo]", anchor_for_udb_doc_inst("foo"))
    assert_equal("%%UDB_DOC_LINK%inst;fo_o;fo.o%%", link_to_udb_doc_inst("fo.o"))
    assert_equal("[#udb:doc:inst:fo_o]", anchor_for_udb_doc_inst("fo.o"))
  end

  def test_csr
    assert_equal("%%UDB_DOC_LINK%csr;foo;foo%%", link_to_udb_doc_csr("foo"))
    assert_equal("[#udb:doc:csr:foo]", anchor_for_udb_doc_csr("foo"))
    assert_equal("%%UDB_DOC_LINK%csr;fo_o;fo.o%%", link_to_udb_doc_csr("fo.o"))
    assert_equal("[#udb:doc:csr:fo_o]", anchor_for_udb_doc_csr("fo.o"))
  end

  def test_csr_field
    assert_equal("%%UDB_DOC_LINK%csr_field;foo.bar;foo.bar%%", link_to_udb_doc_csr_field("foo","bar"))
    assert_equal("[#udb:doc:csr_field:foo:bar]", anchor_for_udb_doc_csr_field("foo","bar"))
    assert_equal("%%UDB_DOC_LINK%csr_field;fo_o.ba_r;fo.o.ba.r%%", link_to_udb_doc_csr_field("fo.o","ba.r"))
    assert_equal("[#udb:doc:csr_field:fo_o:ba_r]", anchor_for_udb_doc_csr_field("fo.o","ba.r"))
  end

  def test_cov_pt
    assert_equal("%%UDB_DOC_COV_PT_LINK%sep;foo_and_bar;foo&bar%%", link_to_udb_doc_cov_pt("sep", "foo&bar"))
    assert_equal("[[udb:doc:cov_pt:sep:foo]]", anchor_for_udb_doc_cov_pt("sep", "foo"))
    assert_equal("%%UDB_DOC_COV_PT_LINK%combo;fo_o;fo.o%%", link_to_udb_doc_cov_pt("combo", "fo.o"))
    assert_equal("[[udb:doc:cov_pt:combo:fo_o]]", anchor_for_udb_doc_cov_pt("combo", "fo.o"))
    assert_raises(ArgumentError) { link_to_udb_doc_cov_pt("bad-org-value","abc") }
  end

  def test_idl_func
    assert_equal("%%UDB_DOC_LINK%func;foo;foo%%", link_to_udb_doc_idl_func("foo"))
    assert_equal("[#udb:doc:func:foo]", anchor_for_udb_doc_idl_func("foo"))
    assert_equal("%%UDB_DOC_LINK%func;fo_o;fo.o%%", link_to_udb_doc_idl_func("fo.o"))
    assert_equal("[#udb:doc:func:fo_o]", anchor_for_udb_doc_idl_func("fo.o"))
  end

  def test_idl_code
    assert_equal("%%IDL_CODE_LINK%inst;foo.bar;foo.bar%%", link_into_idl_inst_code("foo","bar"))
    assert_equal("[#idl:code:inst:foo:bar]", anchor_inside_idl_inst_code("foo","bar"))
    assert_equal("%%IDL_CODE_LINK%inst;fo_o.ba_r;fo.o.ba.r%%", link_into_idl_inst_code("fo.o","ba.r"))
    assert_equal("[#idl:code:inst:fo_o:ba_r]", anchor_inside_idl_inst_code("fo.o","ba.r"))
  end

end

class TestAsciidocUtils < Minitest::Test
  def test_resolve_links_ext
    assert_equal("<<udb:doc:ext:foo,bar>>", AsciidocUtils.resolve_links("%%UDB_DOC_LINK%ext;foo;bar%%"))
    assert_equal("<<udb:doc:ext:foo,foo>>", AsciidocUtils.resolve_links(link_to_udb_doc_ext("foo")))
  end

  def test_resolve_links_ext_param
    assert_equal("<<udb:doc:ext_param:foo:bar,zort>>", AsciidocUtils.resolve_links("%%UDB_DOC_LINK%ext_param;foo.bar;zort%%"))
    assert_equal("<<udb:doc:ext_param:foo:bar,bob>>", AsciidocUtils.resolve_links(link_to_udb_doc_ext_param("foo","bar","bob")))
  end

  def test_resolve_links_inst
    assert_equal("<<udb:doc:inst:foo,bar>>", AsciidocUtils.resolve_links("%%UDB_DOC_LINK%inst;foo;bar%%"))
    assert_equal("<<udb:doc:inst:foo,foo>>", AsciidocUtils.resolve_links(link_to_udb_doc_inst("foo")))
  end

  def test_resolve_links_csr
    assert_equal("<<udb:doc:csr:foo,bar>>", AsciidocUtils.resolve_links("%%UDB_DOC_LINK%csr;foo;bar%%"))
    assert_equal("<<udb:doc:csr:foo,foo>>", AsciidocUtils.resolve_links(link_to_udb_doc_csr("foo")))
  end

  def test_resolve_links_csr_field
    assert_equal("<<udb:doc:csr_field:foo:bar,zort>>", AsciidocUtils.resolve_links("%%UDB_DOC_LINK%csr_field;foo.bar;zort%%"))
    assert_equal("<<udb:doc:csr_field:foo:bar,foo.bar>>", AsciidocUtils.resolve_links(link_to_udb_doc_csr_field("foo","bar")))
  end

  def test_resolve_links_func
    assert_equal("<<udb:doc:func:foo,bar>>", AsciidocUtils.resolve_links("%%UDB_DOC_LINK%func;foo;bar%%"))
    assert_equal("<<udb:doc:func:foo,foo>>", AsciidocUtils.resolve_links(link_to_udb_doc_idl_func("foo")))
  end

  def test_resolve_links_cov_pt
    assert_equal("<<udb:doc:cov_pt:sep:foo,bar>>", AsciidocUtils.resolve_links("%%UDB_DOC_COV_PT_LINK%sep;foo;bar%%"))
    assert_equal("<<udb:doc:cov_pt:sep:foo,foo>>", AsciidocUtils.resolve_links(link_to_udb_doc_cov_pt("sep", "foo")))
    assert_equal("<<udb:doc:cov_pt:combo:foo,bar>>", AsciidocUtils.resolve_links("%%UDB_DOC_COV_PT_LINK%combo;foo;bar%%"))
    assert_equal("<<udb:doc:cov_pt:combo:foo,foo>>", AsciidocUtils.resolve_links(link_to_udb_doc_cov_pt("combo", "foo")))
  end

  def test_resolve_links_idl_code
    assert_equal("<<idl:code:inst:foo:bar,zort>>", AsciidocUtils.resolve_links("%%IDL_CODE_LINK%inst;foo.bar;zort%%"))
    assert_equal("<<idl:code:inst:foo:bar,foo.bar>>", AsciidocUtils.resolve_links(link_into_idl_inst_code("foo","bar")))
  end
end

class TestAntoraUtils < Minitest::Test
  def test_resolve_links_ext
    assert_equal("xref:exts:foo.adoc#udb:doc:ext:foo[bar]", AntoraUtils.resolve_links("%%UDB_DOC_LINK%ext;foo;bar%%"))
    assert_equal("xref:exts:foo.adoc#udb:doc:ext:foo[foo]", AntoraUtils.resolve_links(link_to_udb_doc_ext("foo")))
  end

  def test_resolve_links_ext_param
    assert_equal("xref:exts:foo.adoc#udb:doc:ext_param:foo:bar[[zort]]", AntoraUtils.resolve_links("%%UDB_DOC_LINK%ext_param;foo.bar;[zort]%%"))
    assert_equal("xref:exts:foo.adoc#udb:doc:ext_param:foo:bar[bob]", AntoraUtils.resolve_links(link_to_udb_doc_ext_param("foo","bar","bob")))
  end

  def test_resolve_links_inst
    assert_equal("xref:insts:foo.adoc#udb:doc:inst:foo[bar]", AntoraUtils.resolve_links("%%UDB_DOC_LINK%inst;foo;bar%%"))
    assert_equal("xref:insts:foo.adoc#udb:doc:inst:foo[foo]", AntoraUtils.resolve_links(link_to_udb_doc_inst("foo")))
  end

  def test_resolve_links_csr
    assert_equal("xref:csrs:foo.adoc#udb:doc:csr:foo[bar]", AntoraUtils.resolve_links("%%UDB_DOC_LINK%csr;foo;bar%%"))
    assert_equal("xref:csrs:foo.adoc#udb:doc:csr:foo[foo]", AntoraUtils.resolve_links(link_to_udb_doc_csr("foo")))
  end

  def test_resolve_links_csr_field
    assert_equal("xref:csrs:foo.adoc#udb:doc:csr_field:foo:bar[zort]", AntoraUtils.resolve_links("%%UDB_DOC_LINK%csr_field;foo.bar;zort%%"))
    assert_equal("xref:csrs:foo.adoc#udb:doc:csr_field:foo:bar[foo.bar]", AntoraUtils.resolve_links(link_to_udb_doc_csr_field("foo","bar")))
  end

  def test_resolve_links_func
    assert_equal("xref:funcs:funcs.adoc#udb:doc:func:foo[bar]", AntoraUtils.resolve_links("%%UDB_DOC_LINK%func;foo;bar%%"))
    assert_equal("xref:funcs:funcs.adoc#udb:doc:func:foo[foo]", AntoraUtils.resolve_links(link_to_udb_doc_idl_func("foo")))
  end

  def test_resolve_links_idl_code
    assert_equal("xref:insts:foo.adoc#idl:code:inst:foo:bar[zort]", AntoraUtils.resolve_links("%%IDL_CODE_LINK%inst;foo.bar;zort%%"))
    assert_equal("xref:insts:foo.adoc#idl:code:inst:foo:bar[foo.bar]", AntoraUtils.resolve_links(link_into_idl_inst_code("foo","bar")))
  end
end
