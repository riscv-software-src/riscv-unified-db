#pragma once

namespace udb {
  // base class for a 'view' of a CSR that contains field accessors
  class CsrView {
    public:
    CsrView() {}

    // return the value as a CSR
    virtual XReg value() const = 0;
  };

  // represents the location of a field within a CSR
  struct CsrFieldLocation {
    unsigned msb;
    unsigned lsb;

    constexpr CsrFieldLocation(unsigned _msb, unsigned _lsb) : msb(_msb), lsb(_lsb) {}
    unsigned size() const { return msb - lsb + 1; }
  };

  class CsrFieldBase {
    public:

    struct Type {
      static constexpr unsigned ReadOnly = 1;
      static constexpr unsigned ReadOnlyWithHardwareUpdate = 2;
      static constexpr unsigned ReadWrite = 3;
      static constexpr unsigned ReadWriteRestricted = 4;
      static constexpr unsigned ReadWriteWithHardwareUpdate = 5;
      static constexpr unsigned ReadWriteRestrictedWithHardwareUpdate = 6;
    };

    CsrFieldBase()
    { }

    virtual CsrFieldLocation location() const = 0;

    virtual void reset() = 0;

    // read field out of parent CSR
    virtual uint64_t read() const = 0;

    // read field out of full csr_value (field is located at offset in csr_value)
    virtual uint64_t read(const uint64_t& csr_value) const = 0;

    // write the field, without performing any checks
    virtual void hw_write(const uint64_t &field_write_value) = 0;

    // write the field, applying any restrictions first
    virtual void sw_write(const uint64_t &field_write_value) = 0;

    virtual unsigned type() const = 0;

    bool readOnly() const { return type() == Type::ReadOnly || type() == Type::ReadOnlyWithHardwareUpdate; }
    bool writeable() const { return !readOnly(); }
    bool immutable() const { return type() == Type::ReadOnly; }

    // true when this field is updated by hardware without an explicit software write
    bool hardwareUpdates() const {
      return (
        type() == Type::ReadOnlyWithHardwareUpdate ||
        type() == Type::ReadWriteWithHardwareUpdate ||
        type() == Type::ReadWriteRestrictedWithHardwareUpdate
      );
    }

    // true when only a subset of values are legal for the field
    bool restrictedValues() const {
      return (
        type() == Type::ReadWriteRestricted ||
        type() == Type::ReadWriteRestrictedWithHardwareUpdate
      );
    }

  };

  class HartBase;

  class CsrBase {
    friend class CsrFieldBase;

    public:
    CsrBase() {}

    virtual unsigned address() const = 0;
    virtual const std::string name() const = 0;

    virtual void reset() = 0;

    // read the raw bits of a CSR value
    //
    // some CSRs are shorter than XLEN bits, but none are longer
    // therefore, we can safely use XReg as a value placeholder
    virtual uint64_t hw_read() const = 0;

    // read the overall CSR value, as software would see it through a Zicsr instruction
    //
    // if the CSR presents a different value to software,
    // the CSR can override sw_read() accordingly
    //
    // some CSRs are shorter than XLEN bits, but none are longer
    // therefore, we can safely use XReg as a value placeholder
    virtual uint64_t sw_read() const = 0;

    // tries to write 'value' into the CSR. Checks/conversions will be applied,
    // so the value written may be different than 'value'
    //
    // If the write is illegal, then the function returns false.
    // If the write was accepted (possibly with adjustments), then the function
    // returns true
    virtual bool sw_write(const uint64_t &value) = 0;

    // write all fields as given in 'value'
    //
    // no checks or transformations are applied
    virtual void hw_write(const uint64_t& value) = 0;

  };
}
