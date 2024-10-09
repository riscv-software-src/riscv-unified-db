module TemplateHelpers
  # Insert a hyperlink to an extension.
  #
  # At this point, we insert a placeholder since it will be up
  # to the backend to create a specific link.
  #
  # @param name [#to_s] Name of the extension
  def link_to_ext(name)
    "%%LINK%ext;#{name};#{name}%%"
  end

  # Insert a hyperlink to an instruction.
  #
  # At this point, we insert a placeholder since it will be up
  # to the backend to create a specific link.
  #
  # @param name [#to_s] Name of the instruction
  def link_to_inst(name)
    "%%LINK%inst;#{name};#{name}%%"
  end

  # Insert a hyperlink to a CSR.
  #
  # At this point, we insert a placeholder since it will be up
  # to the backend to create a specific link.
  #
  # @param name [#to_s] Name of the CSR
  def link_to_csr(name)
    "%%LINK%csr;#{name};#{name}%%"
  end

  # Insert a hyperlink to a CSR field.
  #
  # At this point, we insert a placeholder since it will be up
  # to the backend to create a specific link.
  #
  # @param csr_name [#to_s] Name of the CSR
  # @param field_name [#to_s] Name of the CSR field
  def link_to_csr_field(csr_name, field_name)
    "%%LINK%csr_field;#{csr_name}.#{field_name};#{csr_name}.#{field_name}%%"
  end

  # Insert anchor to an extension.
  #
  # At this point, we insert a placeholder since it will be up
  # to the backend to create a specific link.
  #
  # @param name [#to_s] Name of the extension
  def anchor_for_ext(name)
    "[[ext-#{name.gsub(".", "_")}-def]]"
  end

  # Insert anchor to an instruction.
  #
  # At this point, we insert a placeholder since it will be up
  # to the backend to create a specific link.
  #
  # @param name [#to_s] Name of the instruction
  def anchor_for_inst(name)
    "[[inst-#{name.gsub(".", "_")}-def]]"
  end

  # Insert anchor to a CSR.
  #
  # At this point, we insert a placeholder since it will be up
  # to the backend to create a specific link.
  #
  # @param name [#to_s] Name of the CSR
  def anchor_for_csr(name)
    "[[csr-#{name.gsub(".", "_")}-def]]"
  end

  # Insert anchor to a CSR field.
  #
  # At this point, we insert a placeholder since it will be up
  # to the backend to create a specific link.
  #
  # @param csr_name [#to_s] Name of the CSR
  # @param field_name [#to_s] Name of the CSR field
  def anchor_for_csr_field(csr_name, field_name)
    "[[csr_field-#{csr_name.gsub(".", "_")}-#{field_name.gsub(".", "_")}-def]]"
  end
end