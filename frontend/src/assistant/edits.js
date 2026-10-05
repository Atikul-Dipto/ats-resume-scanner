// Applies and reverts the assistant's suggested edits (shape produced by
// backend/app/assistant/tools.py::_resolve) on a builder document.
import { getIn, newKey, setIn } from "../builder/model.js";

export class StaleEdit extends Error {}

function bulletPath(edit) {
  return edit.kind === "replace_project_bullet"
    ? ["projects", edit.project_index, "bullets", edit.bullet_index]
    : ["experience", edit.experience_index, "bullets", edit.bullet_index];
}

export function applyEdit(doc, edit) {
  switch (edit.kind) {
    case "summary":
    case "headline":
      return setIn(doc, ["basics", edit.kind], edit.after);
    case "replace_bullet":
    case "replace_project_bullet": {
      // The resume may have changed since the suggestion; never overwrite the wrong line.
      if (getIn(doc, bulletPath(edit)) !== edit.before) throw new StaleEdit();
      return setIn(doc, bulletPath(edit), edit.after);
    }
    case "add_bullet": {
      const role = doc.experience[edit.experience_index];
      if (!role) throw new StaleEdit();
      const bullets = role.bullets.at(-1) === "" ? role.bullets.slice(0, -1) : role.bullets;
      return setIn(doc, ["experience", edit.experience_index, "bullets"], [...bullets, edit.after]);
    }
    case "add_skills": {
      if (!doc.skills.length) return { ...doc, skills: [{ _key: newKey(), name: "Skills", skills: edit.skills }] };
      const have = new Set(doc.skills.flatMap((g) => g.skills.map((s) => s.toLowerCase())));
      const fresh = edit.skills.filter((s) => !have.has(s.toLowerCase()));
      return setIn(doc, ["skills", 0, "skills"], [...doc.skills[0].skills, ...fresh]);
    }
    default:
      throw new StaleEdit();
  }
}

export function revertEdit(doc, edit) {
  switch (edit.kind) {
    case "summary":
    case "headline":
      return doc.basics[edit.kind] === edit.after ? setIn(doc, ["basics", edit.kind], edit.before) : doc;
    case "replace_bullet":
    case "replace_project_bullet":
      return getIn(doc, bulletPath(edit)) === edit.after ? setIn(doc, bulletPath(edit), edit.before) : doc;
    case "add_bullet": {
      const bullets = doc.experience[edit.experience_index]?.bullets;
      const at = bullets ? bullets.lastIndexOf(edit.after) : -1;
      return at < 0 ? doc : setIn(doc, ["experience", edit.experience_index, "bullets"], bullets.filter((_, i) => i !== at));
    }
    case "add_skills": {
      const added = new Set(edit.skills.map((s) => s.toLowerCase()));
      return { ...doc, skills: doc.skills.map((g) => ({ ...g, skills: g.skills.filter((s) => !added.has(s.toLowerCase())) })) };
    }
    default:
      return doc;
  }
}
