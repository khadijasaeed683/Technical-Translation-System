import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../context/AuthContext.jsx";

const emptyForm = { term: "", domain: "general", canonical_translation: "", aliases: "", roman_urdu_variants: "" };

export default function Glossary() {
  const { user } = useAuth();
  const [terms, setTerms] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState(null);

  async function load() {
    const data = await api.getGlossary();
    setTerms(data);
  }

  useEffect(() => {
    load();
  }, []);

  async function handleAdd(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.createGlossaryTerm({
        term: form.term,
        domain: form.domain,
        canonical_translation: form.canonical_translation,
        aliases: form.aliases ? form.aliases.split(",").map((s) => s.trim()) : [],
        roman_urdu_variants: form.roman_urdu_variants
          ? form.roman_urdu_variants.split(",").map((s) => s.trim())
          : [],
      });
      setForm(emptyForm);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(id) {
    await api.deleteGlossaryTerm(id);
    load();
  }

  return (
    <div className="glossary-page">
      <h1>Glossary</h1>
      <p className="subtle">
        Terms here are consulted by the validation layer to catch jargon that general-purpose
        translators handle literally (Section 5.2 / FR-09).
      </p>

      {user?.is_admin && (
        <form className="glossary-form" onSubmit={handleAdd}>
          <input
            placeholder="Term (e.g. bug)"
            value={form.term}
            onChange={(e) => setForm({ ...form, term: e.target.value })}
            required
          />
          <input
            placeholder="Domain (e.g. CS)"
            value={form.domain}
            onChange={(e) => setForm({ ...form, domain: e.target.value })}
          />
          <input
            placeholder="Canonical translation / handling"
            value={form.canonical_translation}
            onChange={(e) => setForm({ ...form, canonical_translation: e.target.value })}
            required
          />
          <input
            placeholder="Aliases (comma-separated)"
            value={form.aliases}
            onChange={(e) => setForm({ ...form, aliases: e.target.value })}
          />
          <input
            placeholder="Roman Urdu variants (comma-separated)"
            value={form.roman_urdu_variants}
            onChange={(e) => setForm({ ...form, roman_urdu_variants: e.target.value })}
          />
          <button type="submit">Add term</button>
          {error && <p className="form-error">{error}</p>}
        </form>
      )}

      <table className="glossary-table">
        <thead>
          <tr>
            <th>Term</th>
            <th>Domain</th>
            <th>Canonical translation</th>
            <th>Aliases</th>
            {user?.is_admin && <th></th>}
          </tr>
        </thead>
        <tbody>
          {terms.map((t) => (
            <tr key={t.id}>
              <td>{t.term}</td>
              <td>{t.domain}</td>
              <td>{t.canonical_translation}</td>
              <td>{(t.aliases || []).join(", ")}</td>
              {user?.is_admin && (
                <td>
                  <button className="btn-link btn-danger" onClick={() => handleDelete(t.id)}>
                    Delete
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
