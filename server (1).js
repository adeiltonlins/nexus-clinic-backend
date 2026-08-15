require('dotenv').config();
const express = require('express');
const cors = require('cors');
const { createClient } = require('@supabase/supabase-js');
const { GoogleGenerativeAI } = require('@google/generative-ai');

const app = express();
app.use(cors());
app.use(express.json());

// SUPABASE
const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_KEY);

// GEMINI
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const model = genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });

// ===================== HEALTH =====================
app.get('/api/health', (req, res) => res.json({ status: 'ok' }));

// ===================== PATIENTS =====================
app.get('/api/patients', async (req, res) => {
  const { data, error } = await supabase.from('patients').select('*').order('name');
  if (error) return res.status(500).json({ error: error.message });
  res.json(data);
});

app.post('/api/patients', async (req, res) => {
  const { name, phone, email, birth_date, insurance } = req.body;
  const { data, error } = await supabase.from('patients').insert({ name, phone, email, birth_date, insurance }).select().single();
  if (error) return res.status(500).json({ error: error.message });
  res.json(data);
});

// ===================== APPOINTMENTS =====================
app.get('/api/appointments', async (req, res) => {
  const { data, error } = await supabase.from('appointments').select('*, patients(name, phone)').order('date');
  if (error) return res.status(500).json({ error: error.message });
  res.json(data);
});

app.post('/api/appointments', async (req, res) => {
  const { patient_phone, date, time, procedure, dentist, notes } = req.body;
  const { data, error } = await supabase.from('appointments').insert({
    patient_phone, date, time, procedure, dentist, notes, status: 'scheduled'
  }).select().single();
  if (error) return res.status(500).json({ error: error.message });
  res.json(data);
});

// ===================== DASHBOARD =====================
app.get('/api/dashboard', async (req, res) => {
  const today = new Date().toISOString().split('T')[0];
  const [p, a, t, m] = await Promise.all([
    supabase.from('patients').select('*', { count: 'exact', head: true }),
    supabase.from('appointments').select('*', { count: 'exact', head: true }),
    supabase.from('appointments').select('*').eq('date', today),
    supabase.from('messages').select('*', { count: 'exact', head: true })
  ]);
  res.json({
    total_patients: p.count,
    total_appointments: a.count,
    today_appointments: t.data?.length || 0,
    total_messages: m.count
  });
});

// ===================== BOT WEBHOOK =====================
// O bot local chama esta rota quando recebe uma mensagem
app.post('/api/bot/message', async (req, res) => {
  const { phone, text } = req.body;
  if (!phone || !text) return res.status(400).json({ error: 'phone and text required' });

  try {
    // Salva mensagem recebida
    await supabase.from('messages').insert({ phone, message: text, direction: 'received' });

    // Busca paciente
    const { data: patient } = await supabase.from('patients').select('*').eq('phone', phone).single();

    // Busca agendamentos futuros
    const { data: apts } = await supabase.from('appointments').select('*')
      .eq('patient_phone', phone).gte('date', new Date().toISOString().split('T')[0])
      .order('date', { ascending: true }).limit(3);

    // Gera resposta com Gemini
    const prompt = `Voce e a assistente virtual da clinica odontologica. Seja cordial e profissional.
Paciente: ${patient ? patient.name : 'Novo paciente'} (telefone: ${phone})
Proximas consultas: ${apts ? apts.map(a => `${a.date} ${a.time} - ${a.procedure}`).join(', ') : 'Nenhuma agendada'}

Mensagem do paciente: "${text}"

Responda em portugues do Brasil de forma natural e amigavel. Se for sobre agendamento, sugira horarios. Se for duvida, explique brevemente.`;

    const result = await model.generateContent(prompt);
    const reply = result.response.text();

    // Salva resposta
    await supabase.from('messages').insert({ phone, message: reply, direction: 'sent' });

    res.json({ reply, success: true });
  } catch (e) {
    console.error('Erro bot webhook:', e.message);
    res.status(500).json({ 
      error: e.message, 
      reply: 'Desculpe, tive um problema tecnico. Pode repetir?' 
    });
  }
});

// Registra mensagem enviada manualmente pelo bot
app.post('/api/bot/send', async (req, res) => {
  const { phone, message } = req.body;
  if (!phone || !message) return res.status(400).json({ error: 'phone and message required' });
  try {
    await supabase.from('messages').insert({ phone: phone.replace(/\D/g, ''), message, direction: 'sent' });
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`🚀 API rodando na porta ${PORT}`));
