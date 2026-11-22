import { Hero } from "./Hero";
import { Nav } from "./Nav";
import { Careers, FinalCta, Footer, Journey, Trust, Voice, Who } from "./Sections";

/** The public front door. Signed-out visitors land here; signed-in users never see it. */
export function LandingPage() {
  return (
    <div className="bg-bg">
      <Nav />
      <main id="main">
        <Hero />
        <Journey />
        <Careers />
        <Voice />
        <Who />
        <Trust />
        <FinalCta />
      </main>
      <Footer />
    </div>
  );
}
