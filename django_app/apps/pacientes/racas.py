"""Lista de raças por espécie usada no form de Paciente (raça reativa à
espécie escolhida, via Alpine lendo este JSON — ver §5.2 da inventariação do
frontend Vue atual). Lista não exaustiva; "Outra" sempre cobre o resto."""

RACAS_POR_ESPECIE = {
    "cao": [
        "SRD (Vira-lata)", "Labrador", "Golden Retriever", "Poodle", "Bulldog Francês",
        "Bulldog Inglês", "Pastor Alemão", "Rottweiler", "Border Collie", "Beagle",
        "Yorkshire Terrier", "Shih Tzu", "Lhasa Apso", "Chihuahua", "Pinscher",
        "Dachshund (Salsicha)", "Boxer", "Doberman", "Husky Siberiano", "Akita",
        "Shar Pei", "Pug", "Maltês", "Cocker Spaniel", "Basset Hound",
        "Schnauzer", "Fox Paulistinha", "Pit Bull", "Dálmata", "Weimaraner",
        "Outra",
    ],
    "gato": [
        "SRD (Vira-lata)", "Persa", "Siamês", "Maine Coon", "Angorá",
        "Ragdoll", "Sphynx", "Bengal", "British Shorthair", "Munchkin",
        "Himalaio", "Exótico de Pelo Curto", "Norueguês da Floresta", "Vira-lata de Pelo Longo",
        "Outra",
    ],
}
