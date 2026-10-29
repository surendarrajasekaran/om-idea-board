import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

export function App() {
  const [ideas, setIdeas] = useState([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const input = useRef(null);

  async function load(signal) {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/ideas", { signal });
      if (!response.ok)
        throw new Error("Couldn’t load the board. Please try again.");
      setIdeas(await response.json());
    } catch (e) {
      if (e.name !== "AbortError") setError(e.message);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }
  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, []);

  async function submit(event) {
    event.preventDefault();
    if (!content.trim() || saving || loading) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch("/api/ideas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: content.trim() }),
      });
      if (!response.ok)
        throw new Error("Your idea wasn’t saved. Please try again.");
      const idea = await response.json();
      setIdeas((previous) => [idea, ...previous]);
      setContent("");
      setQuery("");
      setNotice("Your idea is on the board. Let’s see where it goes.");
      input.current?.focus();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }
  const filtered = ideas.filter((idea) =>
    idea.content.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Idea Board home">
          <span className="brand-icon">✳</span> idea board
          <span className="brand-dot">.</span>
        </a>
        <span className="topnote">Small sparks. Big possibilities.</span>
        <a
          href="#new-idea"
          className="header-link"
          onClick={() => input.current?.focus()}
        >
          Share an idea <span>↗</span>
        </a>
      </header>
      <main>
        <section className="hero">
          <div>
            <p className="eyebrow">
              <span className="live-dot" /> A SPACE FOR WHAT’S NEXT
            </p>
            <h1>
              Every great thing
              <br />
              starts with <em>an idea.</em>
            </h1>
            <p className="intro">
              The half-formed thoughts. The “what ifs”. The things you can’t
              stop thinking about. They belong here.
            </p>
            <a className="text-link" href="#board">
              Explore the board <span>↓</span>
            </a>
          </div>
          <div className="hero-art" aria-hidden="true">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="spark">✳</div>
            <span className="art-caption">a little spark goes a long way</span>
            <span className="tiny-spark">✦</span>
          </div>
        </section>
        <section className="workspace">
          <aside className="composer" id="new-idea">
            <p className="eyebrow">MAKE YOUR MARK</p>
            <h2>What’s on your mind?</h2>
            <p>
              A new possibility, a better way, or a wild thought. No idea is too
              small.
            </p>
            <form onSubmit={submit}>
              <label htmlFor="idea">Your idea</label>
              <textarea
                ref={input}
                id="idea"
                placeholder="What if we could…"
                maxLength={1000}
                value={content}
                onChange={(e) => setContent(e.target.value)}
                required
                disabled={saving}
              />
              <div className="input-footer">
                <span>Give your idea a little room.</span>
                <span>{content.length}/1000</span>
              </div>
              <button
                type="submit"
                disabled={!content.trim() || saving || loading}
              >
                {saving ? "Sharing…" : "Add to the board"}
                <span>↗</span>
              </button>
            </form>
            <div className="composer-foot">
              <span>✧</span> Good ideas get better when you share them.
            </div>
          </aside>
          <section className="board" id="board">
            <div className="board-heading">
              <div>
                <p className="eyebrow">COLLECTIVE POSSIBILITIES</p>
                <h2>
                  The idea board <span className="count">{ideas.length}</span>
                </h2>
              </div>
              <button
                className="refresh"
                onClick={() => load()}
                disabled={loading || saving}
                aria-label="Refresh ideas"
              >
                ↻
              </button>
            </div>
            <div className="board-tools">
              <span>
                {loading
                  ? "Finding fresh perspectives…"
                  : `${ideas.length} ${ideas.length === 1 ? "spark" : "sparks"} and counting`}
              </span>
              <label className="search">
                <span aria-hidden="true">⌕</span>
                <input
                  aria-label="Search ideas"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Find a spark…"
                />
              </label>
            </div>
            {error && (
              <div role="alert" className="message error">
                {error}
                <button onClick={() => load()}>Retry</button>
              </div>
            )}
            <div
              role="status"
              className={notice ? "message success" : "sr-only"}
            >
              {notice}
            </div>
            {loading ? (
              <div className="empty">
                <span className="loading-spark">✳</span>
                <h3>Gathering the ideas…</h3>
              </div>
            ) : filtered.length ? (
              <div className="ideas-grid">
                {filtered.map((idea, index) => (
                  <article
                    className={`idea-card tone-${index % 4}`}
                    key={idea.id}
                  >
                    <div className="card-top">
                      <span className="idea-number">
                        IDEA {String(idea.id).padStart(3, "0")}
                      </span>
                      <span aria-hidden="true">↗</span>
                    </div>
                    <p>{idea.content}</p>
                    <div className="card-bottom">
                      <span className="card-spark" aria-hidden="true">
                        ✳
                      </span>
                      <time dateTime={idea.created_at}>
                        {new Date(idea.created_at).toLocaleDateString(
                          undefined,
                          { month: "short", day: "numeric", year: "numeric" },
                        )}
                      </time>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              !error && (
                <div className="empty">
                  <span>✳</span>
                  <h3>
                    {query
                      ? "No sparks found."
                      : "The next good idea could be yours."}
                  </h3>
                  <p>
                    {query
                      ? "Try a different word or explore the whole board."
                      : "Be the first to put a thought out into the world."}
                  </p>
                  {query && (
                    <button className="text-link" onClick={() => setQuery("")}>
                      Clear search ↗
                    </button>
                  )}
                </div>
              )
            )}
          </section>
        </section>
      </main>
      <footer>
        <span className="footer-brand">✳ idea board.</span>
        <span>A place to think out loud.</span>
        <span>
          Made for possibilities <span className="footer-spark">✦</span>
        </span>
      </footer>
    </div>
  );
}

if (document.getElementById("root"))
  createRoot(document.getElementById("root")).render(<App />);
