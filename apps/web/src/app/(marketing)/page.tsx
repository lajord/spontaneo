import Link from "next/link";
import { ArrowRight } from "lucide-react";

export default function LandingPage() {
    return (
        <>
            {/* Hero Section */}
            <section className="relative overflow-hidden pt-16 pb-24 md:pt-32 md:pb-32">
                <div className="absolute inset-x-0 top-0 h-[500px] bg-gradient-to-b from-blue-50 to-white pointer-events-none" />

                <div className="relative max-w-7xl mx-auto px-6 text-center space-y-8">

                    {/* Heading */}
                    <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-slate-900 max-w-4xl mx-auto leading-[1.1]">
                        Automatisez votre <br className="hidden md:block" />
                        <span className="text-blue-600">recherche d'emploi</span>
                    </h1>

                    {/* Subtitle */}
                    <p className="text-lg md:text-xl text-slate-600 max-w-2xl mx-auto leading-relaxed">
                        Spontaneo utilise une IA avancée pour générer et envoyer des candidatures spontanées hyper-personnalisées.
                        Décrochez plus d'entretiens, sans effort.
                    </p>

                    {/* CTAs */}
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-6">
                        <Link
                            href="/register"
                            className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-full bg-blue-600 text-white text-base font-semibold shadow-lg shadow-blue-600/20 hover:bg-blue-700 hover:shadow-xl hover:-translate-y-0.5 transition-all w-full sm:w-auto"
                        >
                            Commencer maintenant
                            <ArrowRight className="w-5 h-5" />
                        </Link>
                    </div>

                </div>
            </section>
        </>
    );
}
