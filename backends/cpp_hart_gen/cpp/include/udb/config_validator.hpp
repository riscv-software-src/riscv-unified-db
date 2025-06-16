#pragma once

#include <yaml-cpp/yaml.h>

#include <nlohmann/json-schema.hpp>
#include <regex>

#include "udb/db_data.hxx"

namespace udb {
  class ConfigValidator {
    ConfigValidator() = delete;

   public:
    static nlohmann::json validate(const YAML::Node& config) {
      auto json = yaml_to_json(config);
      if (!json.contains("$schema")) {
        throw std::runtime_error("No $schema in config file");
      }
      fmt::print("{}\n", json.dump());
      std::smatch m;
      std::regex re("^https://riscv.org/udb/schemas/(.*\\.json)");
      std::string schema_path = json["$schema"].template get<std::string>();
      if (!std::regex_match(schema_path, m, re)) {
        throw std::runtime_error("Invalid $schema in config file");
      }
      auto schema = m[1];

      if (schema == "config-0.1.0.json") {
        auto loader = [](const nlohmann::json_uri& uri, nlohmann::json& value) {
          value = nlohmann::json::parse(DbData::SCHEMAS[uri.path().substr(1)]);
        };
        nlohmann::json_schema::json_validator validator(loader);
        try {
          validator.set_root_schema(
              nlohmann::json::parse(DbData::SCHEMAS[schema]));
        } catch (const std::exception* e) {
          throw std::runtime_error(
              "Validation of schema config-0.1.0 failed: " +
              std::string(e->what()));
        }

        try {
          auto default_patch = validator.validate(json);
          return json.patch(default_patch);
        } catch (const std::exception& e) {
          throw std::runtime_error("Config validation failed: " +
                                   std::string(e.what()));
        }
      }
      return json;
    }

   private:
    static nlohmann::json yaml_to_json(const YAML::Node& node) {
      if (node.IsScalar()) {
        union {
          int64_t i;
          double d;
          bool b;
        } scalar;
        std::string s;
        if (YAML::convert<int64_t>::decode(node, scalar.i)) {
          return scalar.i;
          // } else if (YAML::convert<double>::decode(node, scalar.d)) {
          //   return scalar.d;
        } else if (YAML::convert<bool>::decode(node, scalar.b)) {
          return scalar.b;
        } else if (YAML::convert<std::string>::decode(node, s)) {
          return s;
        } else {
          throw std::runtime_error("Unknown scalar type in YAML conversion");
        }
      } else if (node.IsSequence()) {
        nlohmann::json json = nlohmann::json::array();
        for (auto it = node.begin(); it != node.end(); ++it) {
          json.push_back(yaml_to_json(*it));
        }
        return json;
      } else if (node.IsMap()) {
        nlohmann::json json = nlohmann::json::object();
        for (auto&& it : node) {
          json[it.first.as<std::string>()] = yaml_to_json(it.second);
        }
        return json;
      } else if (node.IsNull()) {
        return {nullptr};
      } else {
        throw std::runtime_error("Unknown YAML type in conversion");
      }
    }
  };
}  // namespace udb
