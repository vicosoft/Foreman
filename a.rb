require 'foreman_api'

architectures = ForemanApi::Resources::Architecture.new(
  {
    :base_url => 'http://foreman-url', 
    :oauth => {
      :consumer_key    => 'katello',
      :consumer_secret => "shhhh" 
    }
  },{
    :headers => {
      :foreman_user => "admin",
    }
  })

puts architectures.index.inspect
