#pragma once

#include <cstdint>
#include <string>

#include "udb/enum.hxx"
#include "udb/soc_model.hpp"

namespace udb {
  // represents the location of a field within a CSR
  struct CsrFieldLocation {
    unsigned msb;
    unsigned lsb;

    constexpr CsrFieldLocation(unsigned _msb, unsigned _lsb)
        : msb(_msb), lsb(_lsb) {}
    unsigned size() const { return msb - lsb + 1; }
  };

  class CsrFieldBase {
   public:
    CsrFieldBase() {}

    virtual const CsrFieldLocation location(const unsigned& xlen) const = 0;

    virtual void reset() = 0;

    // read field out of parent CSR, given the effective xlen
    virtual uint64_t hw_read(const unsigned& xlen) const = 0;

    // read field out of full csr_value (field is located at offset in
    // csr_value) given the effective xlen
    virtual uint64_t hw_read(const uint64_t& csr_value,
                             const unsigned& xlen) const = 0;

    // virtual uint64_t sw_read(const unsigned& xlen) const = 0;

    // write the field, without performing any checks
    // given the effective xlen
    virtual void hw_write(const uint64_t& field_write_value,
                          const unsigned& xlen) = 0;

    // write the field, applying any restrictions first
    // given the effective xlen
    // virtual void sw_write(const uint64_t& field_write_value,
    //                       const unsigned& xlen) = 0;

    virtual CsrFieldType type(const unsigned& xlen) const = 0;

    bool readOnly(const unsigned& xlen) const {
      return type(xlen) == CsrFieldType::RO || type(xlen) == CsrFieldType::ROH;
    }
    bool writeable(const unsigned& xlen) const { return !readOnly(xlen); }
    bool immutable(const unsigned& xlen) const {
      return type(xlen) == CsrFieldType::RO;
    }

    // true when this field is updated by hardware without an explicit software
    // write
    bool hardwareUpdates(const unsigned& xlen) const {
      return (type(xlen) == CsrFieldType::ROH ||
              type(xlen) == CsrFieldType::RWH ||
              type(xlen) == CsrFieldType::RWRH);
    }

    // true when only a subset of values are legal for the field
    bool restrictedValues(const unsigned& xlen) const {
      return (type(xlen) == CsrFieldType::RWR ||
              type(xlen) == CsrFieldType::RWRH);
    }
  };

  template <SocModel SocType>
  class HartBase;

  class CsrBase {
    friend class CsrFieldBase;

   public:
    CsrBase() {}

    virtual unsigned address() const = 0;
    virtual const std::string name() const = 0;

    virtual void reset() = 0;

    // the most privileged mode that has access to this csr
    virtual PrivilegeMode mode() const = 0;

    // false if the CSR is read only
    virtual bool writable() const = 0;

    // read the raw bits of a CSR value
    //
    // some CSRs are shorter than XLEN bits, but none are longer
    // therefore, we can safely use XReg as a value placeholder
    virtual uint64_t hw_read(const unsigned& xlen) const = 0;

    // read the overall CSR value, as software would see it through a Zicsr
    // instruction
    //
    // if the CSR presents a different value to software,
    // the CSR can override sw_read() accordingly
    //
    // some CSRs are shorter than XLEN bits, but none are longer
    // therefore, we can safely use XReg as a value placeholder
    virtual uint64_t sw_read(const unsigned& xlen) const = 0;

    // tries to write 'value' into the CSR. Checks/conversions will be applied,
    // so the value written may be different than 'value'
    //
    // If the write is illegal, then the function returns false.
    // If the write was accepted (possibly with adjustments), then the function
    // returns true
    virtual bool sw_write(const uint64_t& value, const unsigned& xlen) = 0;

    // write all fields as given in 'value'
    //
    // no checks or transformations are applied
    virtual void hw_write(const uint64_t& value, const unsigned& xlen) = 0;

    // can't this CSR be implemented when ext is not?
    virtual bool implemented_without_Q_(const ExtensionName&) const = 0;
  };
}  // namespace udb
