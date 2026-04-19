export default function About() {
  const modules = [
    {
      name: "Authentication",
      desc: "Secure admin login using JWT tokens. Only authorized personnel can access the system.",
      icon: "🔐",
    },
    {
      name: "Camera & Video Capture",
      desc: "Live video streaming from browser webcam or connected IP cameras. Real-time frame processing.",
      icon: "📹",
    },
    {
      name: "AI Detection",
      desc: "YOLOv8 deep-learning models for vehicle, helmet, seatbelt, and license plate detection.",
      icon: "🧠",
    },
    {
      name: "Violation Management",
      desc: "Automatic recording of violations with evidence images. Admin review and approval workflow.",
      icon: "📋",
    },
    {
      name: "Admin Dashboard",
      desc: "Centralized monitoring, statistics, and management interface with role-based access.",
      icon: "📊",
    },
  ];

  const tech = [
    { name: "React.js", role: "Frontend UI framework" },
    { name: "Django REST Framework", role: "Backend API" },
    { name: "YOLOv8 (Ultralytics)", role: "Object detection" },
    { name: "EasyOCR", role: "License plate OCR" },
    { name: "OpenCV", role: "Image processing" },
    { name: "PostgreSQL / SQLite", role: "Database" },
    { name: "JWT", role: "Authentication" },
    { name: "TailwindCSS", role: "Styling" },
  ];

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <header className="text-center mb-14">
        <span className="inline-block px-4 py-1.5 text-xs font-semibold text-blue-700 bg-blue-100 rounded-full uppercase tracking-wider">
          About the System
        </span>
        <h1 className="mt-4 text-4xl font-extrabold text-slate-900">
          Vehicle License Plate Recognition &amp; Traffic Violation Detection
        </h1>
        <p className="mt-4 max-w-3xl mx-auto text-slate-600 text-lg">
          VLPR-TVD is an intelligent traffic monitoring solution built on
          object-oriented principles. It automatically recognizes vehicle
          license plates, detects helmet and seatbelt violations in real time,
          and assists authorities in enforcing traffic laws more effectively.
        </p>
      </header>

      <section className="grid md:grid-cols-3 gap-6 mb-16">
        {[
          { k: "Real-time", v: "Frame-level inference" },
          { k: "2 flows", v: "Motorcycle + Car" },
          { k: "Evidence", v: "Auto-captured" },
        ].map((s) => (
          <div
            key={s.k}
            className="bg-white border border-slate-200 rounded-xl p-6 text-center shadow-sm"
          >
            <div className="text-3xl font-extrabold text-blue-600">{s.k}</div>
            <div className="mt-2 text-slate-600">{s.v}</div>
          </div>
        ))}
      </section>

      <section className="mb-16">
        <h2 className="text-2xl font-bold text-slate-900 mb-6">Main Modules</h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {modules.map((m) => (
            <div
              key={m.name}
              className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md transition"
            >
              <div className="text-3xl mb-3">{m.icon}</div>
              <h3 className="font-bold text-slate-900">{m.name}</h3>
              <p className="mt-2 text-sm text-slate-600">{m.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mb-16">
        <h2 className="text-2xl font-bold text-slate-900 mb-6">
          Tools &amp; Technology
        </h2>
        <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-3">
          {tech.map((t) => (
            <div
              key={t.name}
              className="bg-slate-900 text-white rounded-lg p-4"
            >
              <div className="font-bold">{t.name}</div>
              <div className="text-xs text-slate-400 mt-1">{t.role}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-slate-100 rounded-2xl p-8">
        <h2 className="text-xl font-bold text-slate-900 mb-3">
          Project Details
        </h2>
        <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-2 text-sm text-slate-700">
          <div><dt className="inline font-semibold">University:</dt> <dd className="inline">University of Gujrat</dd></div>
          <div><dt className="inline font-semibold">Department:</dt> <dd className="inline">Computer Science</dd></div>
          <div><dt className="inline font-semibold">Session:</dt> <dd className="inline">BSCS 2022–2026</dd></div>
          <div><dt className="inline font-semibold">Advisor:</dt> <dd className="inline">Mr. Adeel Ahmed</dd></div>
          <div className="sm:col-span-2">
            <dt className="inline font-semibold">Team:</dt>{" "}
            <dd className="inline">
              Rajab Nasir (22024119-188), Muhammad Ali (22024119-189), Muhammad
              Haseeb (22024119-153)
            </dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
