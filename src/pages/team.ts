const CONTACT_EMAIL = "raj.ayush@students.iiserpune.ac.in";

interface TeamMember {
  name: string;
  role: string;
  affiliation: string;
  scdldsRole?: string;
  expertise: string;
  image: string;
  imagePosition?: string;
  profile: string;
  email: string;
}

const SCIENTIFIC_TEAM: TeamMember[] = [
  {
    name: "Sandeep Juneja",
    role: "Professor of Computer Science · Centre Director",
    affiliation: "Ashoka University",
    scdldsRole: "Centre Director",
    expertise: "Applied probability, machine learning, and monsoon weather modelling.",
    image: "./team/sandeep-juneja.jpg",
    profile: "https://www.ashoka.edu.in/profile/sandeep-juneja/",
    email: "sandeep.juneja@ashoka.edu.in",
  },
  {
    name: "Bedartha Goswami",
    role: "Assistant Professor · Data Science",
    affiliation: "IISER Pune",
    expertise: "Machine learning for weather and climate, with a focus on complex systems.",
    image: "./team/bedartha-goswami.jpg",
    imagePosition: "center 34%",
    profile:
      "https://www.iiserpune.ac.in/research/department/data-science/people/faculty/regular-faculty/bedartha-goswami/542",
    email: "bedartha.goswami@iiserpune.ac.in",
  },
  {
    name: "Parthasarathi Mukhopadhyay",
    role: "Visiting Faculty · Earth & Environmental Sciences",
    affiliation: "IISER Berhampur · FASc",
    scdldsRole: "Collaborator",
    expertise: "Numerical weather prediction, monsoon modelling, clouds, and convection.",
    image: "./team/parthasarathi-mukhopadhyay.jpg",
    imagePosition: "center 18%",
    profile: "https://www.iiserbpr.ac.in/people/profile/parthasarathym",
    email: "parthasarathym@iiserbpr.ac.in",
  },
  {
    name: "Dr. Manmeet Singh",
    role: "Assistant Professor · Director, DSOC AI Laboratory",
    affiliation: "Western Kentucky University",
    scdldsRole: "Academic visitor",
    expertise: "AI for climate and disaster science, weather prediction, and Earth system modelling.",
    image: "./team/manmeet-singh.jpg",
    imagePosition: "center 18%",
    profile: "https://www.wku.edu/eeas/staff/manmeet_singh",
    email: "manmeet.singh@wku.edu",
  },
  {
    name: "Saptarishi Dhanuka",
    role: "Pre-doctoral Fellow",
    affiliation: "Ashoka University",
    scdldsRole: "Pre-doctoral Fellow",
    expertise: "Artificial intelligence for weather, climate, and data-driven forecasting.",
    image: "./team/saptarishi-dhanuka.jpg",
    imagePosition: "center 20%",
    profile: "https://www.ashoka.edu.in/profile/saptarishi-dhanuka/",
    email: "saptarishi.dhanuka@ashoka.edu.in",
  },
  {
    name: "Bharat",
    role: "Summer Intern · AI Weather Research",
    affiliation: "IISER Pune",
    scdldsRole: "Summer Intern",
    expertise: "MS thesis in AI subseasonal-to-seasonal weather prediction.",
    image:
      "https://scdlds.ashoka.edu.in/wp-content/uploads/2026/06/1000088900.png",
    imagePosition: "center 24%",
    profile: "https://scdlds.ashoka.edu.in/members/bharat/",
    email: "bharat.20221074@students.iiserpune.ac.in",
  },
];

function renderMember(member: TeamMember, index: number): string {
  const imageStyle = member.imagePosition
    ? ` style="object-position: ${member.imagePosition}"`
    : "";

  return `
    <article class="team-person-card">
      <a
        class="team-person-card__portrait"
        href="${member.profile}"
        target="_blank"
        rel="noreferrer"
        aria-label="View ${member.name}'s official profile"
      >
        <img src="${member.image}" alt="${member.name}" loading="eager" decoding="async"${imageStyle} />
        <span class="team-person-card__view" aria-hidden="true">View profile ↗</span>
      </a>
      <div class="team-person-card__body">
        <div class="team-person-card__meta">
          <div class="team-person-card__affiliations">
            <span class="team-card-label">${member.affiliation}</span>
            ${
              member.scdldsRole
                ? `<a
                    class="team-centre-affiliation"
                    href="https://scdlds.ashoka.edu.in/"
                    target="_blank"
                    rel="noreferrer"
                    aria-label="${member.scdldsRole}, Safexpress Centre for Data, Learning and Decision Sciences"
                  ><span aria-hidden="true"></span>SCDLDS · ${member.scdldsRole}</a>`
                : ""
            }
          </div>
          <span class="team-person-card__index" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>
        </div>
        <h3>${member.name}</h3>
        <p class="team-person-card__role">${member.role}</p>
        <p>${member.expertise}</p>
        <div class="team-person-card__links">
          <a href="${member.profile}" target="_blank" rel="noreferrer">Official profile <span aria-hidden="true">↗</span></a>
          <a href="mailto:${member.email}">Email</a>
        </div>
      </div>
    </article>
  `;
}

export function renderTeamPage(container: HTMLElement): void {
  container.innerHTML = `
    <section class="team-page" aria-labelledby="team-title">
      <header class="team-hero">
        <div>
          <span class="team-eyebrow">People behind the forecast</span>
          <h1 id="team-title">The team behind the forecast.</h1>
        </div>
        <div class="team-hero__aside">
          <p>
            S2S Research brings atmospheric science, machine learning, forecast
            verification, and careful public communication together in one
            experimental service.
          </p>
          <dl class="team-hero__stats" aria-label="Team overview">
            <div><dt>07</dt><dd>Team members</dd></div>
            <div><dt>06</dt><dd>SCDLDS affiliated</dd></div>
            <div><dt>01</dt><dd>Shared forecast mission</dd></div>
          </dl>
        </div>
      </header>

      <section class="team-roster" aria-labelledby="team-roster-title">
        <header class="team-section-heading">
          <div>
            <span class="team-eyebrow">Scientific leadership &amp; collaborators</span>
            <h2 id="team-roster-title">Expertise across weather, climate, data, and decisions.</h2>
          </div>
          <p>Centre-connected profiles carry an SCDLDS affiliation badge; institutional profiles and direct contact details remain one click away.</p>
        </header>
        <div class="team-grid">
          ${SCIENTIFIC_TEAM.map(renderMember).join("")}
        </div>
      </section>

      <article class="team-lead team-manager" aria-labelledby="team-manager-name">
        <div class="team-lead__portrait team-lead__portrait--photo">
          <img src="./team/ayush-raj.webp" alt="Ayush Raj" loading="eager" decoding="async" />
          <small>Researcher · MS thesis</small>
        </div>
        <div class="team-lead__content">
          <span class="team-card-label">Research · AI &amp; website maintenance</span>
          <a
            class="team-centre-affiliation team-centre-affiliation--lead"
            href="https://scdlds.ashoka.edu.in/"
            target="_blank"
            rel="noreferrer"
            aria-label="Researcher, Safexpress Centre for Data, Learning and Decision Sciences"
          ><span aria-hidden="true"></span>SCDLDS · Researcher</a>
          <h2 id="team-manager-name">Ayush Raj</h2>
          <p class="team-lead__affiliation">
            IISER Pune · Safexpress Centre for Data, Learning and Decision Sciences
          </p>
          <p>
            Ayush is a researcher completing an MS thesis in AI subseasonal-to-seasonal
            weather prediction. His work spans AI research, forecast evaluation, and
            maintaining the S2S website and its public-facing forecast products.
          </p>
          <div class="team-lead__links">
            <a href="mailto:${CONTACT_EMAIL}">Email Ayush</a>
            <a href="https://in.linkedin.com/in/ayush-raj-7608a424a" target="_blank" rel="noreferrer">
              LinkedIn <span aria-hidden="true">↗</span>
            </a>
          </div>
        </div>
      </article>

      <aside class="team-institution-band" aria-label="Institutional collaboration">
        <div class="team-institution-band__logos">
          <img
            src="./brand/scdlds-centre.png"
            alt="Safexpress Centre for Data, Learning and Decision Sciences"
          />
          <span aria-hidden="true"></span>
          <img src="./brand/ashoka-university.png" alt="Ashoka University" />
        </div>
        <p>
          Developed in association with the Safexpress Centre for Data, Learning
          and Decision Sciences at Ashoka University.
        </p>
        <a href="https://scdlds.ashoka.edu.in/" target="_blank" rel="noreferrer">
          Visit the Centre <span aria-hidden="true">↗</span>
        </a>
      </aside>

      <section class="team-principles" aria-labelledby="team-principles-title">
        <header>
          <span class="team-eyebrow">How we work</span>
          <h2 id="team-principles-title">From research run to public guidance</h2>
        </header>
        <div class="team-principles__grid">
          <article>
            <span>01</span>
            <h3>Scientific provenance</h3>
            <p>Every issue records its initialization source, ensemble size, and valid forecast periods.</p>
          </article>
          <article>
            <span>02</span>
            <h3>Validation before release</h3>
            <p>Forecast packages pass data, checksum, and presentation checks before they can be published.</p>
          </article>
          <article>
            <span>03</span>
            <h3>Transparent limitations</h3>
            <p>Research status, calibration gaps, and source delays stay visible alongside the guidance.</p>
          </article>
        </div>
      </section>

      <section class="team-contact" aria-labelledby="team-contact-title">
        <div>
          <span class="team-card-label">Research enquiries</span>
          <h2 id="team-contact-title">Questions, collaboration, or feedback?</h2>
        </div>
        <a href="mailto:${CONTACT_EMAIL}">Contact the team <span aria-hidden="true">→</span></a>
      </section>
    </section>
  `;
}
