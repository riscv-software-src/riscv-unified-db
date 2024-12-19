module.exports.register = function (registry, context = {}) {
  registry.block("when", function () {
    var self = this;
    self.named("when");
    self.onContexts("paragraph", "open");
    self.positionalAttributes(["condition"]);
    self.process(function (parent, reader, attributes) {
      var condition = attributes.condition;
      let new_block_attrs = {};
      new_block_attrs.role = "when";
      new_block_attrs.name = "when";
      new_block_attrs["textlabel"] = `When ${condition}`;
      let content_model =
        attributes["cloaked-context"] == "paragraph" ? "simple" : "compound";
      return self.createBlock(
        parent,
        "admonition",
        reader.getLines(),
        new_block_attrs,
        { content_model: content_model },
      );
    });
  });
  return registry;
};
