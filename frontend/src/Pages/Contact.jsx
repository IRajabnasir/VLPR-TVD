import { useState } from "react";

export default function Contact() {
  const [form, setForm] = useState({ name: "", email: "", message: "" });
  const [sent, setSent] = useState(false);

  const submit = (e) => {
    e.preventDefault();
    // For D2, this is a client-side placeholder. A real contact endpoint can
    // be added later if needed.
    setSent(true);
  };

  const update = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="max-w-5xl mx-auto px-6 py-12">
      <header className="mb-10 text-center">
        <h1 className="text-4xl font-extrabold text-slate-900">Contact &amp; Help</h1>
        <p className="mt-3 text-slate-600">
          Questions about the system, installation, or a demo? Reach out below.
        </p>
      </header>

      <div className="grid md:grid-cols-2 gap-8">
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <h2 className="font-bold text-slate-900 text-lg mb-4">
            Project Team
          </h2>
          <ul className="space-y-3 text-sm">
            {[
              { name: "Rajab Nasir", id: "22024119-188" },
              { name: "Muhammad Ali", id: "22024119-189" },
              { name: "Muhammad Haseeb", id: "22024119-153" },
            ].map((m) => (
              <li key={m.id} className="flex items-center justify-between border-b last:border-0 border-slate-100 pb-2">
                <div className="font-semibold text-slate-800">{m.name}</div>
                <div className="text-slate-500">{m.id}</div>
              </li>
            ))}
          </ul>

          <div className="mt-6 pt-4 border-t border-slate-100 space-y-2 text-sm text-slate-700">
            <div><span className="font-semibold">Advisor:</span> Mr. Adeel Ahmed</div>
            <div><span className="font-semibold">Department:</span> Computer Science</div>
            <div><span className="font-semibold">University:</span> University of Gujrat</div>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <h2 className="font-bold text-slate-900 text-lg mb-4">Send a message</h2>
          {sent ? (
            <div className="bg-green-50 border border-green-200 text-green-800 rounded-lg p-4 text-sm">
              Thanks, your message has been noted. We'll get back to you
              shortly.
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-3">
              <input
                required
                value={form.name}
                onChange={update("name")}
                placeholder="Your name"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <input
                required
                type="email"
                value={form.email}
                onChange={update("email")}
                placeholder="Your email"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <textarea
                required
                value={form.message}
                onChange={update("message")}
                placeholder="How can we help?"
                rows={5}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                type="submit"
                className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg py-2 transition"
              >
                Send Message
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
