# frozen_string_literal: true

require "English"
require "minitest/autorun"
require "backend_helpers"

include TemplateHelpers

$root ||= (Pathname.new(__FILE__) / ".." / ".." / "..").realpath

class TestBackendHelpers < Minitest::Test
  def test_ext
    assert_equal("%%LINK%ext;foo;foo%%", link_to_ext("foo"))
    assert_equal("[[ext-foo-def]]", anchor_for_ext("foo"))
    assert_equal("%%LINK%ext;fo_o;fo_o%%", link_to_ext("fo.o"))
    assert_equal("[[ext-fo_o-def]]", anchor_for_ext("fo.o"))
  end

  def test_ext_param
    assert_equal("%%LINK%ext_param;foo.bar;bar%%", link_to_ext_param("foo","bar"))
    assert_equal("[[ext_param-foo-bar-def]]", anchor_for_ext_param("foo","bar"))
    assert_equal("%%LINK%ext_param;fo_o.bar;bar%%", link_to_ext_param("fo.o","bar"))
    assert_equal("[[ext_param-fo_o-bar-def]]", anchor_for_ext_param("fo.o","bar"))
    assert_raises(ArgumentError) { link_to_ext_param("foo","ba.r") }
    assert_raises(ArgumentError) { anchor_for_ext_param("foo","ba.r") }
  end

  def test_inst
    assert_equal("%%LINK%inst;foo;foo%%", link_to_inst("foo"))
    assert_equal("[[inst-foo-def]]", anchor_for_inst("foo"))
    assert_equal("%%LINK%inst;fo_o;fo_o%%", link_to_inst("fo.o"))
    assert_equal("[[inst-fo_o-def]]", anchor_for_inst("fo.o"))
  end

  def test_csr
    assert_equal("%%LINK%csr;foo;foo%%", link_to_csr("foo"))
    assert_equal("[[csr-foo-def]]", anchor_for_csr("foo"))
    assert_equal("%%LINK%csr;fo_o;fo_o%%", link_to_csr("fo.o"))
    assert_equal("[[csr-fo_o-def]]", anchor_for_csr("fo.o"))
  end

  def test_csr_field
    assert_equal("%%LINK%csr_field;foo.bar;foo.bar%%", link_to_csr_field("foo","bar"))
    assert_equal("[[csr_field-foo-bar-def]]", anchor_for_csr_field("foo","bar"))
    assert_equal("%%LINK%csr_field;fo_o.ba_r;fo_o.ba_r%%", link_to_csr_field("fo.o","ba.r"))
    assert_equal("[[csr_field-fo_o-ba_r-def]]", anchor_for_csr_field("fo.o","ba.r"))
  end
end

class TestAsciidocUtils < Minitest::Test
  def test_resolve_links_ext
    assert_equal("<<ext-foo-def,bar>>", AsciidocUtils.resolve_links("%%LINK%ext;foo;bar%%"))
    assert_equal("<<ext-foo-def,foo>>", AsciidocUtils.resolve_links(link_to_ext("foo")))
  end

  def test_resolve_links_ext_param
    assert_equal("<<ext_param-foo-bar-def,zort>>", AsciidocUtils.resolve_links("%%LINK%ext_param;foo.bar;zort%%"))
    assert_equal("<<ext_param-foo-bar-def,bar>>", AsciidocUtils.resolve_links(link_to_ext_param("foo","bar")))
  end

  def test_resolve_links_inst
    assert_equal("<<inst-foo-def,bar>>", AsciidocUtils.resolve_links("%%LINK%inst;foo;bar%%"))
    assert_equal("<<inst-foo-def,foo>>", AsciidocUtils.resolve_links(link_to_inst("foo")))
  end

  def test_resolve_links_csr
    assert_equal("<<csr-foo-def,bar>>", AsciidocUtils.resolve_links("%%LINK%csr;foo;bar%%"))
    assert_equal("<<csr-foo-def,foo>>", AsciidocUtils.resolve_links(link_to_csr("foo")))
  end

  def test_resolve_links_csr_field
    assert_equal("<<csr_field-foo-bar-def,zort>>", AsciidocUtils.resolve_links("%%LINK%csr_field;foo.bar;zort%%"))
    assert_equal("<<csr_field-foo-bar-def,foo.bar>>", AsciidocUtils.resolve_links(link_to_csr_field("foo","bar")))
  end

end
