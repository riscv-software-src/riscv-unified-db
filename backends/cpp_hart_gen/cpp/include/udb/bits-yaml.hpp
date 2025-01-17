#pragma once

#include <yaml-cpp/yaml.h>

#include "bits.hpp"

// convert functions so that we can encode/decode a Bits type in YAML
namespace YAML {
  template <unsigned N, bool Signed>
  struct convert<udb::_Bits<N, Signed>> {
    static Node encode(const udb::_Bits<N, Signed>& rhs) {
      Node node;
      node = std::to_string(rhs);
      return node;
    }

    static bool decode(const Node& node, udb::_Bits<N, Signed>& rhs) {
      if (!node.IsScalar()) {
        return false;
      }

      rhs = udb::_Bits<N, Signed>::from_string(node.as<std::string>());
      return true;
    }
  };
}  // namespace YAML
