import Navbar from "./Navbar";

/**
 * Public-page layout: top navbar + content area + footer.
 * Used for Home, About, Contact, and Login pages.
 * Admin pages use <AdminLayout> instead (sidebar).
 */
export default function Layout({ children }) {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      <Navbar />
      <main className="flex-1">{children}</main>
      <footer className="bg-slate-900 text-slate-400 py-6 mt-8">
        <div className="max-w-7xl mx-auto px-6 text-sm flex flex-col md:flex-row md:items-center md:justify-between gap-2">
          <div>© {new Date().getFullYear()} VLPR-TVD — University of Gujrat</div>
          <div className="text-xs">
            Final Year Project · Department of Computer Science
          </div>
        </div>
      </footer>
    </div>
  );
}
