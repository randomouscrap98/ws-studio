const l10n = require("../helpers/l10n").default;

const id = "EVENT_SET_SCREEN_ORIENTATION";
const groups = ["EVENT_GROUP_SCREEN"];

const autoLabel = (fetchArg, input) => {
  return l10n("EVENT_SET_SCREEN_ORIENTATION_LABEL", {
    orientation:
      input.orientation === "vertical"
        ? l10n("FIELD_ORIENTATION_VERTICAL")
        : l10n("FIELD_ORIENTATION_HORIZONTAL"),
  });
};

const fields = [
  {
    key: "orientation",
    label: l10n("FIELD_ORIENTATION"),
    description: l10n("FIELD_ORIENTATION_DESC"),
    type: "select",
    defaultValue: "horizontal",
    options: [
      ["horizontal", l10n("FIELD_ORIENTATION_HORIZONTAL")],
      ["vertical", l10n("FIELD_ORIENTATION_VERTICAL")],
    ],
  },
];

const compile = (input, helpers) => {
  if (helpers.wsc === false) {
    helpers.warnings(
      l10n("WARNING_WSC_ONLY_EVENT", {
        event: id,
      }),
    );
    return;
  }
  const { setScreenOrientation } = helpers;
  setScreenOrientation(
    input.orientation === "vertical" ? "vertical" : "horizontal",
  );
};

module.exports = {
  id,
  description: l10n("EVENT_SET_SCREEN_ORIENTATION_DESC"),
  autoLabel,
  groups,
  fields,
  compile,
};
