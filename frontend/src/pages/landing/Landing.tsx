import { Hero } from "./Hero";
import { Nav } from "./Nav";
import { Careers, Faq, FinalCta, Footer, Journey, Problem, Rules, Trust, Voice, Who } from "./Sections";

/** The public front door. Signed-out visitors land here; signed-in users never see it. */
export function LandingPage() {
  return (
    <div className="bg-white">
      <Nav />
      <main id="main">
        <Hero />
        <Problem />
        <Journey />
        <Careers />
        <Voice />
        <Who />
        <Trust />
        <Rules />
        <Faq />
        <FinalCta />
      </main>
      <Footer />
    </div>
  );
}
