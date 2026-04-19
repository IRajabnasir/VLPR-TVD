import { Link } from "react-router-dom";

export default function Home() {
  return (
    <section className="relative bg-gradient-to-b from-slate-100 via-white to-white overflow-hidden">

      {/* AMBIENT BACKGROUND GLOWS (WOW FACTOR – SUBTLE) */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute top-[-140px] left-[-140px] w-[420px] h-[420px] bg-blue-300/20 rounded-full blur-[140px]" />
        <div className="absolute bottom-[-140px] right-[-140px] w-[420px] h-[420px] bg-amber-300/20 rounded-full blur-[140px]" />
      </div>

      <div className="relative max-w-7xl mx-auto px-6 py-10">

        {/* HERO CONTAINER (UNCHANGED STRUCTURE) */}
        <div className="relative rounded-2xl bg-gradient-to-r from-white via-slate-50 to-white border border-slate-200 shadow-md px-10 py-12">

          {/* subtle professional inner glow */}
          <div className="absolute top-[-60px] right-[-60px] w-96 h-96 bg-blue-200/20 rounded-full blur-3xl"></div>

          <div className="relative grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">

            {/* LEFT CONTENT */}
            <div>
              <span className="inline-block px-4 py-1.5 text-sm font-semibold text-slate-700 bg-slate-200 rounded-full">
                AI-Powered Traffic Intelligence
              </span>

              <h1 className="mt-5 text-[44px] leading-tight font-extrabold text-slate-900">
                Vehicle License Plate
                <span className="block text-blue-600">
                  Recognition & Traffic
                </span>
                Violation Detection System
              </h1>

              <p className="mt-5 text-[17px] text-slate-700 leading-relaxed max-w-xl">
                A next-generation artificial intelligence system designed to
                automatically recognize vehicle license plates and detect traffic
                violations such as over-speeding, red-light breaches, and illegal
                parking — all in real time using advanced computer vision.
              </p>

              {/* ACTION BUTTONS */}
              <div className="mt-7 flex gap-4">

                {/* Admin Login */}
                <Link
                  to="/login"
                  className="px-7 py-3.5 bg-slate-900 text-white rounded-lg text-base font-semibold shadow hover:bg-slate-800 hover:shadow-lg transition inline-flex items-center justify-center"
                >
                  Admin Login
                </Link>

                {/* Learn More */}
                <Link
                  to="/about"
                  className="px-7 py-3.5 border border-slate-300 rounded-lg text-base font-medium text-slate-800 hover:bg-slate-100 transition inline-flex items-center justify-center"
                >
                  Learn More
                </Link>

              </div>
            </div>

            {/* RIGHT CARD */}
            <div className="flex justify-center">
              <div className="w-full max-w-lg bg-white rounded-xl border border-slate-200 shadow-lg p-7">

                <h3 className="text-lg font-semibold text-slate-900 mb-5">
                  Core Capabilities
                </h3>

                <ul className="space-y-4">
                  {[
                    "Automatic License Plate Recognition (ALPR)",
                    "Real-Time Traffic Violation Detection",
                    "AI & Computer Vision-Based Analysis",
                    "Secure Role-Based Monitoring Dashboard",
                    "Scalable Architecture for Law Enforcement",
                  ].map((item, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-3 text-[16px] text-slate-700"
                    >
                      <span className="mt-2 h-2.5 w-2.5 rounded-full bg-blue-600"></span>
                      {item}
                    </li>
                  ))}
                </ul>

              </div>
            </div>

          </div>
        </div>
      </div>
    </section>
  );
}
