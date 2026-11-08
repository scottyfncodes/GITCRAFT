import { Byline } from './Byline.jsx';

export default function App() {
  return (
    <>
      <main className="app">
        <header className="app__head"><h1 className="app__name">{{TITLE}}</h1></header>
        <section className="app__body" id="content" aria-live="polite">Ready.</section>
      </main>
      <footer className="app__foot"><Byline appName="{{TITLE}}" /></footer>
    </>
  );
}
