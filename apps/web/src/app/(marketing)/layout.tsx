import Link from "next/link";
import { ArrowRight, Menu } from "lucide-react";

export default function MarketingLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="min-h-screen bg-white font-sans text-slate-900">
            {/* Header */}
            <header className="fixed top-0 left-0 right-0 z-50 border-b border-slate-100 bg-white/80 backdrop-blur-md">
                <nav className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
                    {/* Logo */}
                    <Link href="/" className="flex items-center gap-2 group">
                        <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-lg shadow-sm group-hover:bg-blue-700 transition-colors">
                            S
                        </div>
                        <span className="text-xl font-bold tracking-tight text-slate-900 group-hover:text-blue-700 transition-colors">
                            Spontaneo
                        </span>
                    </Link>

                    {/* Desktop Nav */}
                    <div className="hidden md:flex items-center gap-10 text-sm font-medium text-slate-600">
                        <a href="#features" className="hover:text-blue-600 transition-colors">
                            Fonctionnalités
                        </a>
                        <a href="#how-it-works" className="hover:text-blue-600 transition-colors">
                            Comment ça marche
                        </a>
                        <a href="#pricing" className="hover:text-blue-600 transition-colors">
                            Tarifs
                        </a>
                    </div>

                    {/* CTA */}
                    <div className="flex items-center gap-4">
                        <Link
                            href="/login"
                            className="hidden md:block text-sm font-medium text-slate-600 hover:text-blue-600 transition-colors"
                        >
                            Se connecter
                        </Link>
                        <Link
                            href="/register"
                            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-blue-600 text-white text-sm font-medium shadow-sm hover:bg-blue-700 hover:shadow transition-all group"
                        >
                            Commencer
                            <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
                        </Link>
                        <button className="md:hidden p-2 text-slate-600">
                            <Menu className="w-6 h-6" />
                        </button>
                    </div>
                </nav>
            </header>

            {/* Main Content */}
            <main className="pt-20 bg-white">{children}</main>

            {/* Footer */}
            <footer className="border-t border-slate-100 bg-slate-50">
                <div className="max-w-7xl mx-auto px-6 py-16">
                    <div className="grid md:grid-cols-4 gap-12 mb-16">
                        <div className="space-y-4 col-span-1 md:col-span-2">
                            <Link href="/" className="flex items-center gap-2">
                                <div className="h-6 w-6 rounded bg-blue-600 flex items-center justify-center text-white font-bold text-xs">
                                    S
                                </div>
                                <span className="font-bold text-slate-900">Spontaneo</span>
                            </Link>
                        </div>

                        <div>
                            <h4 className="font-semibold text-slate-900 mb-4 text-sm">Produit</h4>
                            <ul className="space-y-3 text-sm text-slate-500">
                                <li><a href="#" className="hover:text-blue-600 transition-colors">Fonctionnalités</a></li>
                                <li><a href="#" className="hover:text-blue-600 transition-colors">Tarifs</a></li>
                                <li><a href="#" className="hover:text-blue-600 transition-colors">Témoignages</a></li>
                                <li><a href="#" className="hover:text-blue-600 transition-colors">Roadmap</a></li>
                            </ul>
                        </div>

                        <div>
                            <h4 className="font-semibold text-slate-900 mb-4 text-sm">Légal</h4>
                            <ul className="space-y-3 text-sm text-slate-500">
                                <li><a href="#" className="hover:text-blue-600 transition-colors">Confidentialité</a></li>
                                <li><a href="#" className="hover:text-blue-600 transition-colors">CGU</a></li>
                                <li><a href="#" className="hover:text-blue-600 transition-colors">Mentions légales</a></li>
                                <li><a href="#" className="hover:text-blue-600 transition-colors">Contact</a></li>
                            </ul>
                        </div>
                    </div>

                    <div className="pt-8 border-t border-slate-200 flex flex-col md:flex-row items-center justify-between gap-4">
                        <p className="text-xs text-slate-500">
                            © 2026 Spontaneo. Tous droits réservés.
                        </p>
                    </div>
                </div>
            </footer>
        </div>
    );
}
